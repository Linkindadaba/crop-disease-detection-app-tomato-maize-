import streamlit as st
import tensorflow as tf
from tensorflow.keras.layers import Layer, GlobalAveragePooling2D, GlobalMaxPooling2D, Conv2D, Dense, Reshape, concatenate
from tensorflow.keras.activations import sigmoid
import keras
import numpy as np
from PIL import Image
import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Crop Disease Diagnostic Sandbox",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Plus+Jakarta+Sans:wght@300;400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    h1, h2, h3, .main-title {
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
    }
    
    .main-title {
        font-size: 3rem;
        background: linear-gradient(135deg, #1e824c, #2ecc71);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        font-size: 1.2rem;
        color: #7f8c8d;
        margin-bottom: 2rem;
    }
    
    .card {
        background-color: rgba(255, 255, 255, 0.85);
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
        margin-bottom: 20px;
    }
    
    .metric-card {
        text-align: center;
        padding: 15px;
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        border-radius: 12px;
        border-left: 5px solid #2ecc71;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #2c3e50;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #7f8c8d;
    }
</style>
""", unsafe_allow_html=True)

# --- CLASS DEFINITIONS FOR CUSTOM LAYERS ---
class TripletAttention(Layer):
    def __init__(self, reduction_ratio=16, kernel_size=7, **kwargs):
        super(TripletAttention, self).__init__(**kwargs)
        self.reduction_ratio = reduction_ratio
        self.kernel_size = kernel_size
        self.channel_avg_pool = GlobalAveragePooling2D()
        self.channel_max_pool = GlobalMaxPooling2D()
        self.reshape = Reshape((1, 1, -1))
        self.spatial_conv = Conv2D(filters=1, kernel_size=self.kernel_size, strides=1, padding='same', activation='sigmoid', use_bias=False)

    def build(self, input_shape):
        channels = input_shape[-1]
        self.dense1 = Dense(units=channels // self.reduction_ratio, activation='relu', use_bias=False)
        self.dense2 = Dense(units=channels, activation='sigmoid', use_bias=False)
        super(TripletAttention, self).build(input_shape)

    def call(self, inputs):
        # Channel Attention
        avg_pool = self.channel_avg_pool(inputs)
        max_pool = self.channel_max_pool(inputs)
        avg_out = self.dense2(self.dense1(avg_pool))
        max_out = self.dense2(self.dense1(max_pool))
        channel_attention = sigmoid(avg_out + max_out)
        x = inputs * channel_attention

        # Spatial Attention
        avg_pool_spatial = tf.reduce_mean(x, axis=-1, keepdims=True)
        max_pool_spatial = tf.reduce_max(x, axis=-1, keepdims=True)
        spatial_concat = concatenate([avg_pool_spatial, max_pool_spatial], axis=-1)
        spatial_attention = self.spatial_conv(spatial_concat)
        x = x * spatial_attention
        return x

    def get_config(self):
        config = super(TripletAttention, self).get_config()
        config.update({
            'reduction_ratio': self.reduction_ratio,
            'kernel_size': self.kernel_size,
        })
        return config

# --- PATHS ---
BASE_DIR = Path(__file__).resolve().parent
KERAS_MODEL_PATH = BASE_DIR / "patched_model.keras"
TFLITE_MODEL_PATH = BASE_DIR / "plant_disease_model.tflite"
LABELS_PATH = BASE_DIR / "labels.txt"
DOCX_PATH = BASE_DIR / "crop_disease_detection.docx"

# --- DATASETS AND LABELS ---
@st.cache_data
def load_labels():
    if LABELS_PATH.exists():
        with open(LABELS_PATH, "r") as f:
            labels = [line.strip() for line in f if line.strip()]
        return labels
    else:
        # Fallback classes if labels.txt is missing
        return [
            "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
            "Corn_(maize)___Common_rust_",
            "Corn_(maize)___Northern_Leaf_Blight",
            "Corn_(maize)___healthy",
            "Tomato___Bacterial_spot",
            "Tomato___Early_blight",
            "Tomato___Late_blight",
            "Tomato___Leaf_Mold",
            "Tomato___Septoria_leaf_spot",
            "Tomato___Spider_mites Two-spotted_spider_mite",
            "Tomato___Target_Spot",
            "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
            "Tomato___Tomato_mosaic_virus",
            "Tomato___healthy"
        ]

CLASS_NAMES = load_labels()

# Clean labels for presentation
def clean_class_name(name):
    name = name.replace("___", " - ")
    name = name.replace("_", " ")
    return name

CLEAN_CLASS_NAMES = [clean_class_name(c) for c in CLASS_NAMES]

# --- LOAD MODELS ---
@st.cache_resource
def load_keras_model():
    if not KERAS_MODEL_PATH.exists():
        return None
    try:
        model = keras.models.load_model(
            str(KERAS_MODEL_PATH),
            custom_objects={'TripletAttention': TripletAttention}
        )
        return model
    except Exception as e:
        st.error(f"Error loading Keras model: {e}")
        return None

def load_tflite_interpreter():
    if not TFLITE_MODEL_PATH.exists():
        return None
    try:
        interpreter = tf.lite.Interpreter(model_path=str(TFLITE_MODEL_PATH))
        interpreter.allocate_tensors()
        return interpreter
    except Exception as e:
        st.error(f"Error loading TFLite model: {e}")
        return None

# --- RECOMMENDATIONS DATABASE ---
TREATMENTS = {
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": {
        "description": "Fungal disease causing rectangular, grayish lesions on leaves that run parallel to the veins.",
        "prevention": "Rotate crops with non-grass species, till under infected crop residues, and plant resistant seed hybrids.",
        "chemical": "Apply foliar fungicides such as azoxystrobin or pyraclostrobin if lesions appear on the ear leaf before tasseling.",
        "organic": "Prune infected bottom leaves, apply copper soap spray, and improve soil aeration and organic mulch."
    },
    "Corn_(maize)___Common_rust_": {
        "description": "Fungal disease characterized by powdery, golden-brown pustules on both upper and lower leaf surfaces.",
        "prevention": "Select resistant crop hybrids. Avoid late planting to reduce disease exposure during high humidity peaks.",
        "chemical": "Fungicide sprays (strobilurins/triazoles) are effective but rarely economical unless infection starts very early.",
        "organic": "Spray leaf surfaces with sulfur dust or neem oil to inhibit fungal spore germination."
    },
    "Corn_(maize)___Northern_Leaf_Blight": {
        "description": "Fungal disease producing large, cigar-shaped, grayish-green lesions that can cover entire leaves.",
        "prevention": "Rotate crops for at least 1-2 years, plow crop residue deep, and plant highly resistant hybrids.",
        "chemical": "Apply propiconazole or strobilurin-based fungicides under high-pressure conditions before corn tasseling.",
        "organic": "Improve soil nitrogen levels, clear lower canopy foliage, and apply compost teas to boost plant immunity."
    },
    "Corn_(maize)___healthy": {
        "description": "The maize leaf shows no pathological symptoms and appears strong, green, and healthy.",
        "prevention": "Ensure proper macro and micronutrient supply. Run regular soil testing and keep up standard weeding.",
        "chemical": "No chemical applications required. Avoid preventative fungicide sprays to prevent resistance build-up.",
        "organic": "Apply organic compost, maintain optimal drip irrigation, and use companion planting."
    },
    "Tomato___Bacterial_spot": {
        "description": "Bacterial disease causing small, dark, water-soaked, greasy spots on leaves, stems, and fruit.",
        "prevention": "Use certified disease-free seeds. Avoid overhead watering to keep leaf canopies dry. Rotate crops.",
        "chemical": "Spray copper-based bactericides mixed with mancozeb to overcome copper-resistant bacterial strains.",
        "organic": "Use streptomyces-based bio-fungicides, spray diluted compost extracts, and apply mulch to limit soil splash."
    },
    "Tomato___Early_blight": {
        "description": "Fungal disease showing dark brown spots with characteristic concentric rings (target-like pattern).",
        "prevention": "Prune lower leaves (up to 12 inches from ground) to prevent soil-splash infection. Keep 3-year rotation.",
        "chemical": "Apply chlorothalonil, mancozeb, or copper fungicides at the first sign of lower leaf spotting.",
        "organic": "Apply thick straw mulch, spray baking soda solutions (1 tbsp per gallon with soap), or use neem oil weekly."
    },
    "Tomato___Late_blight": {
        "description": "A rapid, highly destructive oomycete disease causing large dark, greasy lesions with white mold on leaf undersides.",
        "prevention": "Plant resistant cultivars. Keep greenhouse humidity low. Immediately remove and destroy infected plants.",
        "chemical": "Preventative spray of copper fungicides. Apply systemic oomyceticides if disease pressure is high.",
        "organic": "Apply copper octanoate, keep foliage dry, prune heavily for airflow, and destroy wild nightshade weeds."
    },
    "Tomato___Leaf_Mold": {
        "description": "Fungal disease producing pale green spots on leaf tops and velvet-like olive-green growth underneath.",
        "prevention": "Maintain relative humidity below 85% in greenhouses. Maximize spacing and install ventilation fans.",
        "chemical": "Apply protectant fungicides like chlorothalonil or sulfur-based sprays under humid conditions.",
        "organic": "Spray with potassium bicarbonate or dilute milk sprays, prune lower branches, and use drip lines instead of overhead sprinklers."
    },
    "Tomato___Septoria_leaf_spot": {
        "description": "Fungal disease characterized by numerous small, circular spots with light gray centers and dark borders.",
        "prevention": "Avoid working in wet foliage. Stake and cage tomato plants. Remove crop debris at the end of the season.",
        "chemical": "Apply chlorothalonil or copper fungicides at 7-10 day intervals during warm, wet weather.",
        "organic": "Apply organic mulch, spray with copper-based organic soaps, and prune infected leaves early."
    },
    "Tomato___Spider_mites Two-spotted_spider_mite": {
        "description": "Tiny arachnid pests causing fine yellow stippling, leaf bronzing, and delicate webbing on leaf undersides.",
        "prevention": "Keep plants well-hydrated; dusty, dry conditions trigger rapid mite outbreaks. Avoid broad-spectrum insecticides.",
        "chemical": "Apply specific miticides (e.g. abamectin or bifenazate) to target mite colonies on leaf undersides.",
        "organic": "Release predatory mites (Phytoseiulus persimilis), spray leaves with insecticidal soap or horticultural neem oil."
    },
    "Tomato___Target_Spot": {
        "description": "Fungal disease causing small circular spots with concentric target-like rings, often confused with early blight.",
        "prevention": "Improve row spacing for maximum sunlight penetration. Keep foliage dry. Eradicate solanaceous weeds.",
        "chemical": "Foliar sprays of azoxystrobin, chlorothalonil, or copper fungicides are highly effective.",
        "organic": "Apply Bacillus subtilis bio-fungicides and use drip irrigation to prevent water pooling on foliage."
    },
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": {
        "description": "Severe viral infection transmitted by silverleaf whiteflies, resulting in stunted growth and upward-curling yellow leaves.",
        "prevention": "Protect young seedlings with insect-proof netting. Control whiteflies using yellow sticky traps.",
        "chemical": "Apply systemic insecticides (e.g. imidacloprid) to target whitefly vectors, especially on young plants.",
        "organic": "Spray insecticidal oil or soap to control whitefly nymphs, introduce lacewings, and immediately bag/remove infected plants."
    },
    "Tomato___Tomato_mosaic_virus": {
        "description": "Highly infectious virus causing mottled green and yellow patches, leaf twisting, and severely reduced yields.",
        "prevention": "Use certified virus-free seed. Wash hands and tools with soap and milk when handling plants. Avoid tobacco use.",
        "chemical": "No chemical viricides exist. Control is entirely dependent on sanitation and vector management.",
        "organic": "Immediately pull, bag, and burn infected plants. Disinfect stakes and tools in a 10% trisodium phosphate solution."
    },
    "Tomato___healthy": {
        "description": "The tomato leaf exhibits a deep green, uniform appearance with strong veins and no active lesions.",
        "prevention": "Continue standard fertilizer balance (nitrogen/phosphorus/potassium). Monitor leaf undersides weekly for early pests.",
        "chemical": "No chemical applications required. Practice preventative crop protection through sanitation.",
        "organic": "Apply calcium supplements to prevent blossom end rot, water consistently at the base, and prune suckers."
    }
}

# --- PREPROCESSING ---
def preprocess_image(image, target_size=(224, 224)):
    img = image.convert('RGB')
    img = img.resize(target_size, Image.Resampling.BILINEAR)
    img_array = np.array(img, dtype=np.float32)
    img_array = np.expand_dims(img_array, axis=0)
    return img_array

# --- GRAD-CAM FUNCTION ---
def compute_gradcam(img_tensor, model):
    try:
        # Reconstruct layer pointers from sequential model
        backbone = model.layers[1]
        triplet_att = model.layers[2]
        gap = model.layers[3]
        dense1 = model.layers[4]
        dropout = model.layers[5]
        dense2 = model.layers[6]
        
        # Find last conv layer in backbone
        last_conv_layer_name = None
        for layer in reversed(backbone.layers):
            if 'conv' in layer.name.lower() or isinstance(layer, tf.keras.layers.Conv2D):
                last_conv_layer_name = layer.name
                break
        
        if not last_conv_layer_name:
            return None, None
            
        # Create a model for the backbone that outputs both the last conv activations and final features
        backbone_grad_model = tf.keras.models.Model(
            inputs=[backbone.inputs],
            outputs=[backbone.get_layer(last_conv_layer_name).output, backbone.output]
        )
        
        with tf.GradientTape() as tape:
            conv_outputs, backbone_features = backbone_grad_model(img_tensor)
            x = triplet_att(backbone_features)
            x = gap(x)
            x = dense1(x)
            x = dropout(x, training=False)
            preds = dense2(x)
            
            pred_index = tf.argmax(preds[0])
            class_channel = preds[:, pred_index]
            
        grads = tape.gradient(class_channel, conv_outputs)
        pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        
        conv_outputs = conv_outputs[0]
        heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
        heatmap = tf.squeeze(heatmap)
        
        # Apply ReLU and normalize
        heatmap = tf.maximum(heatmap, 0)
        max_val = tf.math.reduce_max(heatmap)
        if max_val > 0:
            heatmap = heatmap / max_val
            
        return heatmap.numpy(), pred_index.numpy()
    except Exception as e:
        st.warning(f"Grad-CAM generation failed: {e}")
        return None, None

# --- APP NAVIGATION ---
st.sidebar.markdown("<h2 style='text-align: center; color: #2ecc71;'>Sandbox Menu</h2>", unsafe_allow_html=True)
page = st.sidebar.radio(
    "Go To:",
    ["Single Leaf Diagnosis", "Batch Accuracy Evaluation", "Thesis Chapters Hub", "Project Presentation Slides", "Defense Practice Quiz", "SUS Usability Survey & Analytics"]
)

model_backend = st.sidebar.selectbox(
    "Select Model Backend:",
    ["Keras Model (patched_model.keras)", "TFLite Model (plant_disease_model.tflite)"]
)

# Load selected model
keras_model = None
tflite_interpreter = None

if model_backend.startswith("Keras"):
    with st.spinner("Loading Keras Model with Triplet Attention (FP32)..."):
        keras_model = load_keras_model()
    if keras_model:
        st.sidebar.success("Keras Model Active!")
    else:
        st.sidebar.error("Failed to load Keras model.")
else:
    with st.spinner("Loading TFLite Quantized Model (INT8)..."):
        tflite_interpreter = load_tflite_interpreter()
    if tflite_interpreter:
        st.sidebar.success("TFLite INT8 Model Active!")
    else:
        st.sidebar.error("Failed to load TFLite model.")

st.sidebar.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
conf_threshold = st.sidebar.slider(
    "Diagnostic Confidence Threshold (%):",
    min_value=50,
    max_value=95,
    value=80,
    step=5,
    help="Higher threshold boosts app accuracy and precision by rejecting low-confidence, blurry, or out-of-distribution leaf scans."
)

# --- PAGE 1: SINGLE LEAF DIAGNOSIS ---
if page == "Single Leaf Diagnosis":
    st.markdown("<h1 class='main-title'>Crop Disease Diagnostic Sandbox</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Upload a leaf image of tomato or maize to identify crop diseases offline and view pathological recommendations.</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>Upload Crop Leaf</h3>", unsafe_allow_html=True)
        
        input_method = st.radio("Select input method:", ["File Upload", "Live Camera"], horizontal=True, key="input_method_radio")
        
        image = None
        if input_method == "File Upload":
            uploaded_file = st.file_uploader("Drag and drop your image here (JPG, JPEG, PNG)", type=["jpg", "jpeg", "png"])
            if uploaded_file:
                image = Image.open(uploaded_file)
        else:
            camera_photo = st.camera_input("Take a photo of the leaf")
            if camera_photo:
                image = Image.open(camera_photo)
        
        if image:
            st.image(image, caption="Leaf Image", width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        if image:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3>Diagnostic Report</h3>", unsafe_allow_html=True)
            
            with st.spinner("Analyzing pathological details..."):
                preds = None
                pred_class_idx = -1
                
                if model_backend.startswith("Keras") and keras_model:
                    img_tensor = preprocess_image(image, target_size=(224, 224))
                    preds = keras_model.predict(img_tensor, verbose=0)[0]
                    pred_class_idx = np.argmax(preds)
                    
                    # Compute Grad-CAM
                    heatmap, cam_idx = compute_gradcam(img_tensor, keras_model)
                    
                elif tflite_interpreter:
                    img_tensor = preprocess_image(image, target_size=(224, 224))
                    input_details = tflite_interpreter.get_input_details()
                    output_details = tflite_interpreter.get_output_details()
                    
                    tflite_interpreter.set_tensor(input_details[0]['index'], img_tensor)
                    tflite_interpreter.invoke()
                    outputs = tflite_interpreter.get_tensor(output_details[0]['index'])[0]
                    
                    # Convert to probs if quantized
                    output_detail = output_details[0]
                    if output_detail['dtype'] in (np.int8, np.uint8):
                        scale, zero_point = output_detail.get('quantization', (0.0, 0))
                        if scale > 0:
                            outputs = (outputs.astype(np.float32) - zero_point) * scale
                    
                    preds = outputs
                    pred_class_idx = np.argmax(preds)
                    heatmap = None
                
                if preds is not None:
                    # Display top predictions
                    top_indices = np.argsort(preds)[::-1][:3]
                    top_class = CLASS_NAMES[pred_class_idx]
                    top_conf = float(preds[pred_class_idx] * 100)
                    is_healthy = "healthy" in top_class.lower()
                    
                    # Check against selected confidence threshold
                    if top_conf < conf_threshold:
                        st.markdown(f"""
                        <div style='background-color: #fff3e0; border-left: 6px solid #f57c00; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
                            <span style='color: #e65100; font-weight: bold; font-size: 0.95rem;'>⚠️ UNCERTAIN / LOW CONFIDENCE DIAGNOSIS ({top_conf:.1f}% < {conf_threshold}%)</span>
                            <h4 style='margin: 5px 0 0 0; color: #2c3e50;'>Tentative: {CLEAN_CLASS_NAMES[pred_class_idx]}</h4>
                            <p style='margin: 8px 0 0 0; color: #555; font-size: 0.88rem;'>
                                Diagnostic confidence is below your safety threshold (<b>{conf_threshold}%</b>). To prevent false positives from glare, blur, or noisy backgrounds:
                            </p>
                            <ul style='margin-top: 4px; color: #666; font-size: 0.85rem; line-height: 1.4;'>
                                <li>Reposition camera closer to a single diseased leaf spot.</li>
                                <li>Ensure bright, indirect natural lighting without direct specular glare.</li>
                                <li>Or lower the confidence slider in the sidebar if inspecting subtle early-stage lesions.</li>
                            </ul>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Main Result Badge
                        color = "#2ecc71" if is_healthy else "#e74c3c"
                        badge_text = "HEALTHY CROP" if is_healthy else "DISEASE DETECTED"
                        
                        st.markdown(f"""
                        <div style='background-color: {color}15; border-left: 6px solid {color}; padding: 15px; border-radius: 8px; margin-bottom: 20px;'>
                            <span style='color: {color}; font-weight: bold; font-size: 0.9rem;'>{badge_text}</span>
                            <h4 style='margin: 5px 0 0 0; color: #2c3e50;'>{CLEAN_CLASS_NAMES[pred_class_idx]}</h4>
                            <span style='font-size: 1.8rem; font-weight: 800; color: #2c3e50;'>{top_conf:.1f}%</span> <span style='color: #7f8c8d;'>confidence</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Progress Bars for top 3
                    st.markdown("<h4>Probability Distribution</h4>", unsafe_allow_html=True)
                    for idx in top_indices:
                        conf = preds[idx] * 100
                        st.write(f"**{CLEAN_CLASS_NAMES[idx]}**")
                        st.progress(int(conf))
                    
                    # Treatment recommendations
                    st.markdown("<hr>", unsafe_allow_html=True)
                    st.markdown("<h3>Pathological Recommendations</h3>", unsafe_allow_html=True)
                    
                    rec = TREATMENTS.get(top_class)
                    if rec:
                        st.markdown(f"**Description:** {rec['description']}")
                        st.markdown(f"**Prevention Measures:** {rec['prevention']}")
                        if not is_healthy:
                            st.markdown(f"**Chemical Treatments:** {rec['chemical']}")
                            st.markdown(f"**Organic Treatments:** {rec['organic']}")
                    else:
                        st.info("No recommendations mapped for this class.")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Display Grad-CAM overlay if available
            if model_backend.startswith("Keras") and heatmap is not None:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.markdown("<h3>Grad-CAM Explainability Map</h3>", unsafe_allow_html=True)
                st.markdown("<p style='color: #7f8c8d;'>Red overlay highlights leaf regions that contributed most to the AI's diagnostic prediction.</p>", unsafe_allow_html=True)
                
                # Resize heatmap and overlay using PIL and matplotlib to avoid cv2 dependency
                original_img = np.array(image.resize((224, 224)))
                heatmap_pil = Image.fromarray(np.uint8(255 * heatmap))
                heatmap_resized = heatmap_pil.resize((224, 224), Image.Resampling.BILINEAR)
                heatmap_resized_arr = np.array(heatmap_resized) / 255.0
                
                # Apply jet colormap
                cmap = plt.get_cmap('jet')
                heatmap_color = cmap(heatmap_resized_arr)[:, :, :3]  # Keep RGB, ignore Alpha
                heatmap_color_uint8 = np.uint8(255 * heatmap_color)
                
                # Mathematical overlay (equivalent to cv2.addWeighted)
                overlay_img = np.uint8(original_img * 0.6 + heatmap_color_uint8 * 0.4)
                
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    st.image(original_img, caption="Original Input (224x224)", width="stretch")
                with col_i2:
                    st.image(overlay_img, caption="Attention Overlay Heatmap", width="stretch")
                st.markdown("</div>", unsafe_allow_html=True)
            elif model_backend.startswith("TFLite"):
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.info("Switch to the **Keras Model** backend in the sidebar to compute and visualize **Grad-CAM explainability heatmaps**.")
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Please upload an image to begin the diagnosis.")

# --- PAGE 2: BATCH ACCURACY EVALUATION ---
elif page == "Batch Accuracy Evaluation":
    st.markdown("<h1 class='main-title'>Batch Accuracy Evaluation & Dataset Tester</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Select a local folder or upload a batch of leaf images to evaluate multi-image predictions, accuracy metrics, and confusion matrices.</p>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h3>Select Batch Input Source</h3>", unsafe_allow_html=True)
    
    batch_source = st.radio(
        "Choose how to load your evaluation batch:",
        [
            "Upload Multiple Files / Browse Folder",
            "Local Directory Path (Server / Local Machine)",
            "Sample Project Media Folder"
        ],
        horizontal=True,
        key="batch_source_radio"
    )
    
    # Structure to hold (filename, Image_object)
    batch_images = []
    
    if batch_source == "Upload Multiple Files / Browse Folder":
        uploaded_batch = st.file_uploader(
            "Browse your computer to select multiple image files or drag & drop a batch of leaf photos:",
            type=["jpg", "jpeg", "png", "bmp", "webp"],
            accept_multiple_files=True,
            key="batch_file_uploader"
        )
        if uploaded_batch:
            st.info(f"Loaded **{len(uploaded_batch)}** files from your browser selection.")
            for f in uploaded_batch:
                try:
                    img = Image.open(f)
                    batch_images.append((f.name, img))
                except Exception:
                    pass
                    
    elif batch_source == "Local Directory Path (Server / Local Machine)":
        default_dir = BASE_DIR.parent / "testImages"
        if not default_dir.exists():
            default_dir = BASE_DIR / "media"
            
        test_dir_str = st.text_input("Enter Local Directory Path:", value=str(default_dir))
        test_dir = Path(test_dir_str)
        
        if test_dir.exists():
            image_paths = [p for p in test_dir.iterdir() if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}]
            st.info(f"Found **{len(image_paths)}** images in `{test_dir}`.")
            for p in image_paths:
                try:
                    img = Image.open(p)
                    batch_images.append((p.name, img))
                except Exception:
                    pass
        else:
            st.error(f"Directory not found: `{test_dir_str}`")
            
    elif batch_source == "Sample Project Media Folder":
        media_dir = BASE_DIR / "media"
        if media_dir.exists():
            image_paths = [p for p in media_dir.iterdir() if p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}]
            st.info(f"Found **{len(image_paths)}** sample project images in `{media_dir}`.")
            for p in image_paths:
                try:
                    img = Image.open(p)
                    batch_images.append((p.name, img))
                except Exception:
                    pass
        else:
            st.warning("Sample media directory not found.")
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    if batch_images:
        if st.button("Run Batch Evaluation Engine", key="run_batch_eval_btn"):
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3>Evaluating Batch Images...</h3>", unsafe_allow_html=True)
            
            # Ground truth keyword mapping for automatic ground truth matching
            code_mapping = {
                "cercospora": 0, "gray_leaf": 0, "glsp": 0,
                "rust": 1,
                "northern": 2, "nlb": 2,
                "r.s_hl": 3, "corn_healthy": 3, "maize_healthy": 3,
                "bacterial": 4,
                "erly": 5, "early_blight": 5,
                "late_blight": 6,
                "mold": 7, "leaf_mold": 7,
                "septoria": 8,
                "spider": 9, "spider_mites": 9,
                "target": 10, "target_spot": 10,
                "ylcv": 11, "yellow_leaf_curl": 11,
                "mosaic": 12, "mosaic_virus": 12,
                "gh_hl": 13, "tomato_healthy": 13, "healthy": 13
            }
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            y_true = []
            y_pred = []
            detailed_results = []
            
            correct_count = 0
            total_eval = 0
            matched_labels_count = 0
            
            for idx, (fname, img) in enumerate(batch_images):
                fname_lower = fname.lower()
                expected_idx = -1
                
                # Match filename keywords
                for key, val in code_mapping.items():
                    if key in fname_lower:
                        expected_idx = val
                        break
                        
                total_eval += 1
                
                # Run Model Inference
                if model_backend.startswith("Keras") and keras_model:
                    img_tensor = preprocess_image(img, target_size=(224, 224))
                    preds = keras_model.predict(img_tensor, verbose=0)[0]
                    pred_idx = np.argmax(preds)
                    conf = float(preds[pred_idx] * 100)
                elif tflite_interpreter:
                    img_tensor = preprocess_image(img, target_size=(224, 224))
                    input_details = tflite_interpreter.get_input_details()
                    output_details = tflite_interpreter.get_output_details()
                    tflite_interpreter.set_tensor(input_details[0]['index'], img_tensor)
                    tflite_interpreter.invoke()
                    outputs = tflite_interpreter.get_tensor(output_details[0]['index'])[0]
                    
                    output_detail = output_details[0]
                    if output_detail['dtype'] in (np.int8, np.uint8):
                        scale, zero_point = output_detail.get('quantization', (0.0, 0))
                        if scale > 0:
                            outputs = (outputs.astype(np.float32) - zero_point) * scale
                    pred_idx = np.argmax(outputs)
                    conf = float(outputs[pred_idx] * 100)
                else:
                    pred_idx = -1
                    conf = 0.0
                    
                is_correct = False
                if expected_idx != -1:
                    matched_labels_count += 1
                    y_true.append(expected_idx)
                    y_pred.append(pred_idx)
                    is_correct = (pred_idx == expected_idx)
                    if is_correct:
                        correct_count += 1
                        
                gt_text = CLEAN_CLASS_NAMES[expected_idx] if expected_idx != -1 else "Unlabelled / General Batch"
                correct_text = "Yes" if is_correct else ("No" if expected_idx != -1 else "N/A")
                
                detailed_results.append({
                    "File Name": fname,
                    "Ground Truth": gt_text,
                    "Predicted Pathology": CLEAN_CLASS_NAMES[pred_idx] if pred_idx != -1 else "Error",
                    "Confidence": f"{conf:.1f}%",
                    "Correct": correct_text
                })
                
                progress_val = int((idx + 1) / len(batch_images) * 100)
                progress_bar.progress(progress_val)
                status_text.text(f"Evaluated {idx+1}/{len(batch_images)} images: {fname}")
                
            # Metric Summary Cards
            st.markdown("<hr>", unsafe_allow_html=True)
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            
            accuracy = (correct_count / matched_labels_count * 100) if matched_labels_count > 0 else 0.0
            avg_conf = np.mean([float(r["Confidence"].replace("%", "")) for r in detailed_results]) if detailed_results else 0.0
            
            with col_m1:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-value'>{total_eval}</div>
                    <div class='metric-label'>Total Images Processed</div>
                </div>
                """, unsafe_allow_html=True)
            with col_m2:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='metric-value'>{matched_labels_count}</div>
                    <div class='metric-label'>Ground Truth Matched</div>
                </div>
                """, unsafe_allow_html=True)
            with col_m3:
                st.markdown(f"""
                <div class='metric-card' style='border-left-color: #2ecc71;'>
                    <div class='metric-value'>{accuracy:.1f}%</div>
                    <div class='metric-label'>Matched Accuracy</div>
                </div>
                """, unsafe_allow_html=True)
            with col_m4:
                st.markdown(f"""
                <div class='metric-card' style='border-left-color: #3498db;'>
                    <div class='metric-value'>{avg_conf:.1f}%</div>
                    <div class='metric-label'>Avg Batch Confidence</div>
                </div>
                """, unsafe_allow_html=True)
                
            # Confusion Matrix (if matched labels exist)
            if matched_labels_count > 0 and len(y_true) == len(y_pred):
                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown("<h3>Confusion Matrix</h3>", unsafe_allow_html=True)
                
                unique_labels = sorted(list(set(y_true) | set(y_pred)))
                cm = np.zeros((len(unique_labels), len(unique_labels)), dtype=int)
                
                idx_map = {orig_idx: i for i, orig_idx in enumerate(unique_labels)}
                for t, p in zip(y_true, y_pred):
                    cm[idx_map[t], idx_map[p]] += 1
                
                fig, ax = plt.subplots(figsize=(9, 7))
                sns.heatmap(
                    cm, 
                    annot=True, 
                    fmt="d", 
                    cmap="Greens",
                    xticklabels=[CLEAN_CLASS_NAMES[i].split(" - ")[-1] for i in unique_labels],
                    yticklabels=[CLEAN_CLASS_NAMES[i].split(" - ")[-1] for i in unique_labels],
                    ax=ax
                )
                plt.xlabel("Predicted Class")
                plt.ylabel("True Ground Truth Class")
                plt.title("Batch Evaluation Confusion Matrix")
                st.pyplot(fig)
                plt.close(fig)
                
            # Detailed Predictions Table with Download
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown("<h3>Detailed Batch Predictions Table</h3>", unsafe_allow_html=True)
            
            import pandas as pd
            df_results = pd.DataFrame(detailed_results)
            st.dataframe(df_results, use_container_width=True)
            
            csv_batch = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Batch Results (.csv)",
                data=csv_batch,
                file_name="batch_diagnostic_results.csv",
                mime="text/csv"
            )
            st.markdown("</div>", unsafe_allow_html=True)

# --- PAGE 3: THESIS CHAPTERS HUB ---
elif page == "Thesis Chapters Hub":
    if "fullscreen_thesis" not in st.session_state:
        st.session_state.fullscreen_thesis = False

    # Inject Fullscreen CSS when enabled
    if st.session_state.fullscreen_thesis:
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        .main .block-container {
            max-width: 98% !important;
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        header[data-testid="stHeader"] {
            display: none !important;
        }
        footer {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

    st.markdown("<h1 class='main-title'>Thesis Chapters Hub</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Preview and download the completed Chapters 1 to 5 compiled dynamically from your Word report.</p>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h3>Chapters Compiler</h3>", unsafe_allow_html=True)
    
    if DOCX_PATH.exists():
        st.success("Found updated report docx: **crop_disease_detection.docx**")
        
        with open(DOCX_PATH, "rb") as file:
            btn = st.download_button(
                label="Download Completed Report (.docx)",
                data=file,
                file_name="crop_disease_detection.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        st.markdown("<hr>", unsafe_allow_html=True)
        
        top_c1, top_c2 = st.columns([3, 1])
        with top_c1:
            st.markdown("<h3>Chapter Preview</h3>", unsafe_allow_html=True)
        with top_c2:
            fs_top_label = "Exit Fullscreen" if st.session_state.fullscreen_thesis else "Fullscreen Mode"
            if st.button(fs_top_label, width="stretch", key="fs_thesis_top_btn"):
                st.session_state.fullscreen_thesis = not st.session_state.fullscreen_thesis
                st.rerun()
        
        # Define Chapters list
        chapters_list = [
            "Project Contributors",
            "Abstract",
            "Table of Contents",
            "Chapter 1: Introduction", 
            "Chapter 2: Literature Review", 
            "Chapter 3: Methodology", 
            "Chapter 4: Results and Discussion", 
            "Chapter 5: Summary, Conclusions & Recommendations",
            "References",
            "Appendix A: SUS Instrument & Results",
            "Appendix B: Offline SQLite Database Schema",
            "Appendix C: Source Code Excerpts",
            "Appendix D: Disease & Remedy Dictionary"
        ]
        
        # Initialize chapter index in session state
        if "chapter_index" not in st.session_state:
            st.session_state.chapter_index = 0
            
        if "chapter_selector" not in st.session_state or st.session_state.chapter_selector not in chapters_list:
            st.session_state.chapter_selector = chapters_list[st.session_state.chapter_index]

        def on_radio_change():
            selected = st.session_state.chapter_selector
            st.session_state.chapter_index = chapters_list.index(selected)

        def go_prev():
            if st.session_state.chapter_index > 0:
                st.session_state.chapter_index -= 1
                st.session_state.chapter_selector = chapters_list[st.session_state.chapter_index]

        def go_next():
            if st.session_state.chapter_index < len(chapters_list) - 1:
                st.session_state.chapter_index += 1
                st.session_state.chapter_selector = chapters_list[st.session_state.chapter_index]

        # Select Chapter
        chap_selection = st.radio(
            "Select Chapter to Preview:", 
            chapters_list,
            key="chapter_selector",
            on_change=on_radio_change
        )
        
        # Load and parse document
        @st.cache_data(ttl=60)
        def parse_docx_chapters(path_str):
            import docx
            doc = docx.Document(path_str)
            
            chaps = {
                "Abstract": [],
                "Chapter 1: Introduction": [],
                "Chapter 2: Literature Review": [],
                "Chapter 3: Methodology": [],
                "Chapter 4: Results and Discussion": [],
                "Chapter 5: Summary, Conclusions & Recommendations": [],
                "References": [],
                "Appendix A: SUS Instrument & Results": [],
                "Appendix B: Offline SQLite Database Schema": [],
                "Appendix C: Source Code Excerpts": [],
                "Appendix D: Disease & Remedy Dictionary": []
            }
            
            curr_chap = None
            for p in doc.paragraphs:
                txt = p.text.strip()
                if not txt:
                    continue
                
                txt_lower = txt.lower()
                if txt_lower == "abstract":
                    curr_chap = "Abstract"
                    continue
                elif "chapter one" in txt_lower:
                    curr_chap = "Chapter 1: Introduction"
                    continue
                elif "chapter two" in txt_lower:
                    curr_chap = "Chapter 2: Literature Review"
                    continue
                elif "chapter three" in txt_lower:
                    curr_chap = "Chapter 3: Methodology"
                    continue
                elif "chapter four" in txt_lower:
                    curr_chap = "Chapter 4: Results and Discussion"
                    continue
                elif "chapter five" in txt_lower:
                    curr_chap = "Chapter 5: Summary, Conclusions & Recommendations"
                    continue
                elif "references" in txt_lower and len(txt) < 15:
                    curr_chap = "References"
                    continue
                elif "appendix a" in txt_lower:
                    curr_chap = "Appendix A: SUS Instrument & Results"
                    continue
                elif "appendix b" in txt_lower:
                    curr_chap = "Appendix B: Offline SQLite Database Schema"
                    continue
                elif "appendix c" in txt_lower:
                    curr_chap = "Appendix C: Source Code Excerpts"
                    continue
                elif "appendix d" in txt_lower:
                    curr_chap = "Appendix D: Disease & Remedy Dictionary"
                    continue
                
                if curr_chap:
                    chaps[curr_chap].append({
                        "text": txt,
                        "style": p.style.name if p.style else "Normal"
                    })
            return chaps

        try:
            chapters_data = parse_docx_chapters(str(DOCX_PATH))
            
            if chap_selection == "Project Contributors":
                st.markdown("""<div style='background: linear-gradient(135deg, #1b5e20, #2e7d32); color: white; padding: 25px; border-radius: 16px; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); text-align: center;'><h2 style='color: #ffffff; margin-bottom: 4px; font-weight: 800;'>SUNYANI TECHNICAL UNIVERSITY</h2><h4 style='color: #a5d6a7; margin-top: 0; font-weight: 500;'>FACULTY OF APPLIED SCIENCE AND TECHNOLOGY</h4><h5 style='color: #e8f5e9; margin-top: 0; font-style: italic;'>DEPARTMENT OF COMPUTER SCIENCE</h5><hr style='border: 0; height: 1px; background: rgba(255,255,255,0.3); margin: 15px 0;'><h3 style='color: #ffd54f; font-weight: 700; margin: 0;'>1.1 MOBILE BASED CROP DISEASE DETECTION AND ADVISORY SYSTEM</h3></div>""", unsafe_allow_html=True)
                
                st.markdown("### Group Project Members & Engineering Roles")
                
                col_c1, col_c2 = st.columns(2)
                
                with col_c1:
                    st.markdown("""<div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #f57f17; margin-bottom: 15px;'><h4 style='margin:0; color:#1b5e20;'>Ntiamoah Prince Agyei</h4><p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH220135</b></p><span style='display:inline-block; padding:4px 10px; background:#f57f17; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>DevOps & Model Deployment Engineer</span></div>""", unsafe_allow_html=True)
                    
                    st.markdown("""<div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #2e7d32; margin-bottom: 15px;'><h4 style='margin:0; color:#1b5e20;'>Adjei Sarfo Joseph</h4><p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH221244</b></p><span style='display:inline-block; padding:4px 10px; background:#2e7d32; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>Lead AI & Machine Learning Researcher</span></div>""", unsafe_allow_html=True)
                    
                with col_c2:
                    st.markdown("""<div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #388e3c; margin-bottom: 15px;'><h4 style='margin:0; color:#1b5e20;'>Abdul Wasiu Abubakr</h4><p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH220035</b></p><span style='display:inline-block; padding:4px 10px; background:#388e3c; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>Full-Stack & Mobile Software Engineer</span></div>""", unsafe_allow_html=True)
                    
                    st.markdown("""<div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #43a047; margin-bottom: 15px;'><h4 style='margin:0; color:#1b5e20;'>Lomotey Nathaniel Julian</h4><p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH220073</b></p><span style='display:inline-block; padding:4px 10px; background:#43a047; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>Data Engineer & XAI Evaluation Specialist</span></div>""", unsafe_allow_html=True)
                
                st.markdown("""<div style='background-color: #fffde7; padding: 18px; border-radius: 12px; border: 2px solid #ffd54f; text-align: center; margin-top: 10px;'><h4 style='margin:0; color:#f57f17;'>Project Supervisor & Academic Advisor</h4><h3 style='margin: 5px 0 0 0; color:#2e7d32;'>Mr. Solomon</h3><p style='margin:2px 0 0 0; color:#666;'>Department of Computer Science, Sunyani Technical University</p></div>""", unsafe_allow_html=True)
            elif chap_selection == "Table of Contents":
                st.markdown("## TABLE OF CONTENTS")
                st.markdown("""
                <div style='background-color: #f9fbe7; padding: 25px; border-radius: 12px; border: 1px solid #c8e6c9;'>
                    <ul style='list-style-type: none; padding-left: 0; line-height: 1.9;'>
                        <li style='margin-bottom: 12px;'><strong style='font-size: 18px; color: #1b5e20;'>Table of Contents</strong></li>
                        <li style='margin-left: 10px; margin-top: 8px;'><strong style='color: #2e7d32;'>Chapter 1: Introduction</strong>
                            <ul style='list-style-type: circle; margin-left: 20px; color: #455a64;'>
                                <li>1.1 Background of the Study</li>
                                <li>1.2 Statement of the Problem</li>
                                <li>1.3 Objectives of the Study</li>
                                <li>1.4 Scope of the Project</li>
                                <li>1.5 Limitations of the Study</li>
                                <li>1.6 Significance of the Project</li>
                                <li>1.7 Organization of the Work</li>
                            </ul>
                        </li>
                        <li style='margin-left: 10px; margin-top: 12px;'><strong style='color: #2e7d32;'>Chapter 2: Literature Review</strong>
                            <ul style='list-style-type: circle; margin-left: 20px; color: #455a64;'>
                                <li>2.1 Overview of Crop Diseases</li>
                                <li>2.2 Deep Learning Architectures for Crop Disease Detection</li>
                                <li>2.3 Attention Mechanisms in CNNs</li>
                                <li>2.4 Explainable Artificial Intelligence (XAI) in Agriculture</li>
                                <li>2.5 Mobile Deployment of Deep Learning Models</li>
                                <li>2.6 Usability Evaluation in Agricultural AI Applications</li>
                                <li>2.7 Summary and Research Gaps</li>
                            </ul>
                        </li>
                        <li style='margin-left: 10px; margin-top: 12px;'><strong style='color: #2e7d32;'>Chapter 3: Methodology</strong>
                            <ul style='list-style-type: circle; margin-left: 20px; color: #455a64;'>
                                <li>3.1 Overview of Research Design</li>
                                <li>3.2 Dataset Selection and Acquisition</li>
                                <li>3.3 Data Preprocessing and Augmentation</li>
                                <li>3.4 Attention-Enhanced EfficientNet-B0 Architecture</li>
                                <li>3.5 Triplet Attention Mechanism Implementation</li>
                                <li>3.6 Two-Phase Transfer Learning Strategy</li>
                                <li>3.7 Evaluation Metrics</li>
                                <li>3.8 Model Export and Quantization</li>
                                <li>3.9 Grad-CAM Explainability</li>
                                <li>3.10 Flutter Mobile Application Development</li>
                                <li>3.11 System Usability Evaluation</li>
                            </ul>
                        </li>
                        <li style='margin-left: 10px; margin-top: 12px;'><strong style='color: #2e7d32;'>Chapter 4: Results and Discussion</strong>
                            <ul style='list-style-type: circle; margin-left: 20px; color: #455a64;'>
                                <li>4.1 Results</li>
                                <ul style='list-style-type: square; margin-left: 20px; color: #546e7a;'>
                                    <li>4.1.1 Evaluation Environment & Dataset Split</li>
                                    <li>4.1.2 Model Training Performance & Classification Metrics</li>
                                    <li>4.1.3 Model Quantization & Mobile CPU Latency Benchmarks</li>
                                    <li>4.1.4 Visual Explainability via Grad-CAM Heatmaps</li>
                                    <li>4.1.5 Mobile Application UI Implementation</li>
                                    <li>4.1.6 Field Usability Evaluation Results</li>
                                </ul>
                                <li>4.2 Discussion</li>
                                <ul style='list-style-type: square; margin-left: 20px; color: #546e7a;'>
                                    <li>4.2.1 State-of-the-Art Literature Comparison</li>
                                    <li>4.2.2 Verification of Research Gap Fulfillment</li>
                                    <li>4.2.3 Software Engineering & Agronomic Implications</li>
                                </ul>
                            </ul>
                        </li>
                        <li style='margin-left: 10px; margin-top: 12px;'><strong style='color: #2e7d32;'>Chapter 5: Summary, Conclusions and Recommendations</strong>
                            <ul style='list-style-type: circle; margin-left: 20px; color: #455a64;'>
                                <li>5.1 Summary of Findings</li>
                                <li>5.2 Conclusions</li>
                                <li>5.3 Limitations of the Study</li>
                                <li>5.4 Recommendations for Future Work</li>
                            </ul>
                        </li>
                        <li style='margin-left: 10px; margin-top: 12px;'><strong style='color: #2e7d32;'>References</strong></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
            else:
                selected_paragraphs = chapters_data[chap_selection]
                st.markdown(f"## {chap_selection.upper()}")
                
                # Helper to display figures
                def show_figure_if_matched(text):
                    text_lower = text.lower()
                    media_dir = BASE_DIR / "media"
                    
                    if "figure 3.1" in text_lower:
                        st.image(str(media_dir / "image1.png"), caption=text, width="stretch")
                    elif "figure 3.2" in text_lower:
                        st.image(str(media_dir / "image2.png"), caption=text, width="stretch")
                    elif "figure 3.3" in text_lower:
                        st.image(str(media_dir / "image3.png"), caption=text, width="stretch")
                    elif "figure 3.4" in text_lower:
                        st.image(str(media_dir / "image4.png"), caption=text, width="stretch")
                    elif "figure 3.5" in text_lower:
                        st.image(str(media_dir / "image5.png"), caption=text, width="stretch")
                    elif "figure 3.6" in text_lower:
                        st.image(str(media_dir / "image6.png"), caption=text, width="stretch")
                    elif "figure 3.7" in text_lower:
                        st.image(str(media_dir / "image7.png"), caption=text, width="stretch")
                    elif "figure 3.8" in text_lower:
                        if "classification report" in text_lower:
                            st.image(str(media_dir / "image8.png"), caption=text, width="stretch")
                        elif "mobile application architecture" in text_lower or "mobile app" in text_lower:
                            st.image(str(media_dir / "image11.png"), caption=text, width="stretch")
                    elif "figure 3.9" in text_lower:
                        st.image(str(media_dir / "image9.png"), caption=text, width="stretch")
                    elif "figure 4.1" in text_lower or "training completion report" in text_lower or "colab" in text_lower or "3.9.1" in text_lower:
                        if (media_dir / "image10.png").exists():
                            st.image(str(media_dir / "image10.png"), caption=text, width="stretch")
                    elif "figure 4.2" in text_lower:
                        st.image(str(media_dir / "image8.png"), caption=text, width="stretch")
                    elif "figure 4.3" in text_lower:
                        st.image(str(media_dir / "image9.png"), caption=text, width="stretch")
                    elif "figure 4.4" in text_lower or "home screen" in text_lower or "camera" in text_lower:
                        if (media_dir / "image12.png").exists():
                            st.image(str(media_dir / "image12.png"), caption=text, width="stretch")
                    elif "figure 4.5" in text_lower or "diagnostic report" in text_lower or "treatment" in text_lower:
                        if (media_dir / "image13.png").exists():
                            st.image(str(media_dir / "image13.png"), caption=text, width="stretch")
                    elif "figure 4.6" in text_lower or "historical" in text_lower or "full report" in text_lower:
                        if (media_dir / "image14.png").exists():
                            st.image(str(media_dir / "image14.png"), caption=text, width="stretch")

                # Helper to display tables
                def show_table_if_matched(text):
                    text_lower = text.lower()
                    if "table 3.1" in text_lower:
                        st.table([
                            {"Disease Class": "Tomato - Healthy", "Crop": "Tomato", "Total Images": "1,590", "Split (Train/Val/Test)": "1,113 / 239 / 238"},
                            {"Disease Class": "Tomato - Early Blight", "Crop": "Tomato", "Total Images": "1,000", "Split (Train/Val/Test)": "700 / 150 / 150"},
                            {"Disease Class": "Tomato - Late Blight", "Crop": "Tomato", "Total Images": "1,909", "Split (Train/Val/Test)": "1,336 / 287 / 286"},
                            {"Disease Class": "Tomato - Bacterial Spot", "Crop": "Tomato", "Total Images": "2,127", "Split (Train/Val/Test)": "1,489 / 319 / 319"},
                            {"Disease Class": "Tomato - Leaf Mold", "Crop": "Tomato", "Total Images": "952", "Split (Train/Val/Test)": "666 / 143 / 143"},
                            {"Disease Class": "Tomato - Septoria Leaf Spot", "Crop": "Tomato", "Total Images": "1,771", "Split (Train/Val/Test)": "1,240 / 266 / 265"},
                            {"Disease Class": "Tomato - Spider Mites", "Crop": "Tomato", "Total Images": "1,676", "Split (Train/Val/Test)": "1,173 / 252 / 251"},
                            {"Disease Class": "Tomato - Target Spot", "Crop": "Tomato", "Total Images": "1,404", "Split (Train/Val/Test)": "983 / 211 / 210"},
                            {"Disease Class": "Tomato - Yellow Leaf Curl Virus", "Crop": "Tomato", "Total Images": "5,357", "Split (Train/Val/Test)": "3,750 / 804 / 803"},
                            {"Disease Class": "Tomato - Mosaic Virus", "Crop": "Tomato", "Total Images": "373", "Split (Train/Val/Test)": "261 / 56 / 56"},
                            {"Disease Class": "Maize - Healthy", "Crop": "Maize", "Total Images": "1,162", "Split (Train/Val/Test)": "813 / 175 / 174"},
                            {"Disease Class": "Maize - Common Rust", "Crop": "Maize", "Total Images": "1,192", "Split (Train/Val/Test)": "834 / 179 / 179"},
                            {"Disease Class": "Maize - Gray Leaf Spot", "Crop": "Maize", "Total Images": "513", "Split (Train/Val/Test)": "359 / 77 / 77"},
                            {"Disease Class": "Maize - Northern Leaf Blight", "Crop": "Maize", "Total Images": "985", "Split (Train/Val/Test)": "690 / 148 / 147"},
                        ])
                    elif "table 3.2" in text_lower:
                        st.table([
                            {"Augmentation Technique": "Rotation", "Parameter": "±30°", "Rationale": "Simulates different leaf orientations in field photos"},
                            {"Augmentation Technique": "Width Shift", "Parameter": "±15%", "Rationale": "Accounts for off-centre leaf placement in camera frame"},
                            {"Augmentation Technique": "Height Shift", "Parameter": "±15%", "Rationale": "Handles vertical variation in leaf capture angle"},
                            {"Augmentation Technique": "Shear", "Parameter": "±15%", "Rationale": "Simulates perspective distortion from camera tilt"},
                            {"Augmentation Technique": "Zoom", "Parameter": "±20%", "Rationale": "Replicates varying distances from leaf to camera lens"},
                            {"Augmentation Technique": "Horizontal Flip", "Parameter": "Enabled", "Rationale": "Leaf disease patterns are symmetric across vertical axis"},
                            {"Augmentation Technique": "Vertical Flip", "Parameter": "Enabled", "Rationale": "Accounts for inverted leaf captures in field conditions"},
                            {"Augmentation Technique": "Brightness Range", "Parameter": "[0.7 – 1.3]", "Rationale": "Simulates outdoor lighting variability"},
                            {"Augmentation Technique": "Channel Shift", "Parameter": "±25.0", "Rationale": "Models colour variation across different smartphone cameras"},
                        ])
                    elif "table 3.3" in text_lower:
                        st.table([
                            {"Hyperparameter": "Input Image Size", "Value": "224 x 224 x 3", "Justification": "Default EfficientNet-B0 input resolution"},
                            {"Hyperparameter": "Batch Size", "Value": "64", "Justification": "Fully utilize T4 GPU VRAM"},
                            {"Hyperparameter": "Phase 1 Learning Rate", "Value": "1e-3", "Justification": "Standard Adam LR for classification head"},
                            {"Hyperparameter": "Phase 2 Learning Rate", "Value": "1e-5", "Justification": "Low LR for fine-tuning backbone"},
                            {"Hyperparameter": "Phase 1 Epochs", "Value": "20", "Justification": "Head convergence with frozen backbone"},
                            {"Hyperparameter": "Phase 2 Epochs", "Value": "15 (max)", "Justification": "Early stopping prevents overfitting"},
                            {"Hyperparameter": "Label Smoothing", "Value": "0.1", "Justification": "Regularizes overconfident predictions"},
                            {"Hyperparameter": "L2 Regularization", "Value": "1e-4", "Justification": "Reduces dense layer weight magnitudes"},
                        ])
                    elif "table 3.4" in text_lower:
                        st.table([
                            {"Format": "Keras (.h5)", "Size": "~20 MB", "Precision": "FP32", "Deployment Target": "Training / Server"},
                            {"Format": "Keras Native (.keras)", "Size": "~20 MB", "Precision": "FP32", "Deployment Target": "Model serialization / reload"},
                            {"Format": "TFLite FP32", "Size": "~20 MB", "Precision": "FP32", "Deployment Target": "Mobile (baseline)"},
                            {"Format": "TFLite INT8 (adopted)", "Size": "~5 MB", "Precision": "INT8 weights, FP32 I/O", "Deployment Target": "Mobile edge - 4x smaller"},
                        ])
                    elif "table 4.1" in text_lower:
                        st.table([
                            {"Class": "Corn (maize) - Cercospora Leaf Spot", "Precision": "0.971", "Recall": "0.961", "F1-Score": "0.966"},
                            {"Class": "Corn (maize) - Common Rust", "Precision": "0.994", "Recall": "0.994", "F1-Score": "0.994"},
                            {"Class": "Corn (maize) - Northern Leaf Blight", "Precision": "0.968", "Recall": "0.974", "F1-Score": "0.971"},
                            {"Class": "Corn (maize) - Healthy", "Precision": "0.994", "Recall": "0.994", "F1-Score": "0.994"},
                            {"Class": "Tomato - Bacterial Spot", "Precision": "0.984", "Recall": "0.987", "F1-Score": "0.986"},
                            {"Class": "Tomato - Early Blight", "Precision": "0.961", "Recall": "0.953", "F1-Score": "0.957"},
                            {"Class": "Tomato - Late Blight", "Precision": "0.972", "Recall": "0.979", "F1-Score": "0.975"},
                            {"Class": "Tomato - Leaf Mold", "Precision": "0.986", "Recall": "0.979", "F1-Score": "0.983"},
                            {"Class": "Tomato - Septoria Leaf Spot", "Precision": "0.974", "Recall": "0.981", "F1-Score": "0.977"},
                            {"Class": "Tomato - Spider Mites", "Precision": "0.980", "Recall": "0.976", "F1-Score": "0.978"},
                            {"Class": "Tomato - Target Spot", "Precision": "0.958", "Recall": "0.962", "F1-Score": "0.960"},
                            {"Class": "Tomato - Yellow Leaf Curl Virus", "Precision": "0.993", "Recall": "0.994", "F1-Score": "0.994"},
                            {"Class": "Tomato - Mosaic Virus", "Precision": "0.964", "Recall": "0.946", "F1-Score": "0.955"},
                            {"Class": "Tomato - Healthy", "Precision": "0.992", "Recall": "0.992", "F1-Score": "0.992"},
                        ])
                    elif "table 4.2" in text_lower:
                        st.table([
                            {"Model Format": "Keras Baseline (FP32)", "File Size": "20.3 MB", "Test Accuracy": "98.24%", "Inference CPU (PC)": "42 ms", "Inference CPU (Mobile)": "310 ms"},
                            {"Model Format": "TFLite Quantized (INT8)", "File Size": "5.1 MB", "Test Accuracy": "97.85%", "Inference CPU (PC)": "11 ms", "Inference CPU (Mobile)": "92 ms"},
                        ])
                    elif "table 4.3" in text_lower:
                        st.table([
                            {"Study / Method": "Mohanty et al. (2016) [AlexNet]", "Model Size": "~200 MB", "Accuracy": "93.50%", "Mobile Latency": "Cloud only", "XAI (Grad-CAM)": "No", "Offline App": "No"},
                            {"Study / Method": "Too et al. (2019) [DenseNet-121]", "Model Size": "~130 MB", "Accuracy": "97.20%", "Mobile Latency": "Cloud only", "XAI (Grad-CAM)": "No", "Offline App": "No"},
                            {"Study / Method": "Agarwal et al. (2021) [MobileNetV2 FP32]", "Model Size": "~14 MB", "Accuracy": "95.80%", "Mobile Latency": "280 ms", "XAI (Grad-CAM)": "No", "Offline App": "Baseline"},
                            {"Study / Method": "Proposed Framework [Triplet EffNet + INT8]", "Model Size": "5.1 MB", "Accuracy": "97.85%", "Mobile Latency": "92 ms", "XAI (Grad-CAM)": "Yes", "Offline App": "Yes (Flutter + SQLite)"},
                        ])
                    elif "table 4.4" in text_lower:
                        st.table([
                            {"Identified Gap (Chapter 1)": "Gap 1: High Model Footprint", "Technical Solution": "Triplet Attention EffNet-B0 + INT8 Quantization", "Verification Outcome": "COMPLETED: 5.1 MB size (74.8% reduction), 97.85% accuracy"},
                            {"Identified Gap (Chapter 1)": "Gap 2: Cloud Dependency & Rural Latency", "Technical Solution": "Native TFLite Mobile Client (Flutter)", "Verification Outcome": "COMPLETED: 92 ms offline inference on mobile CPU"},
                            {"Identified Gap (Chapter 1)": "Gap 3: Black-Box Model Distrust", "Technical Solution": "Grad-CAM Attention Heatmap overlays", "Verification Outcome": "COMPLETED: Visual lesion validation in UI"},
                            {"Identified Gap (Chapter 1)": "Gap 4: Lack of Actionable Offline Advice", "Technical Solution": "Offline SQLite Database (DbService)", "Verification Outcome": "COMPLETED: Instant chemical/organic/prevention remedies"},
                            {"Identified Gap (Chapter 1)": "Gap 5: Absence of Integrated End-to-End System", "Technical Solution": "Flutter Mobile Client + Streamlit Sandbox", "Verification Outcome": "COMPLETED: Full software app with 76.5 SUS rating"}
                        ])

                # Render paragraphs
                for item in selected_paragraphs:
                    p_text = item["text"]
                    p_style = item["style"]
                    
                    is_fig = any(keyword in p_text.lower() for keyword in ["figure 3.", "figure 4."])
                    is_tbl = any(keyword in p_text.lower() for keyword in ["table 3.", "table 4."])
                    
                    if is_fig:
                        st.markdown(f"<p style='color: #7f8c8d; font-style: italic; text-align: center;'>{p_text}</p>", unsafe_allow_html=True)
                        show_figure_if_matched(p_text)
                    elif is_tbl:
                        st.markdown(f"<p style='color: #2c3e50; font-weight: 500;'>{p_text}</p>", unsafe_allow_html=True)
                        show_table_if_matched(p_text)
                    elif p_style.startswith("Heading"):
                        st.markdown(f"### {p_text}")
                    elif p_text[0].isdigit() and (p_text[1] == '.' or (len(p_text) > 2 and p_text[2] == '.')):
                        st.markdown(f"**{p_text}**")
                    elif chap_selection == "References":
                        st.markdown(f"<p style='text-align: justify; padding-left: 30px; text-indent: -30px; line-height: 1.5; margin-bottom: 12px; font-size: 13.5px;'>{p_text}</p>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<p style='text-align: justify; line-height: 1.6;'>{p_text}</p>", unsafe_allow_html=True)

            # Bottom Navigation Buttons (Next / Prev)
            st.markdown("<hr>", unsafe_allow_html=True)
            nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
            
            with nav_col1:
                if st.session_state.chapter_index > 0:
                    st.button("Previous Chapter", width="stretch", on_click=go_prev)
            with nav_col2:
                fs_bot_label = "Exit Fullscreen" if st.session_state.fullscreen_thesis else "Fullscreen Mode"
                if st.button(fs_bot_label, width="stretch", key="fs_thesis_bot_btn"):
                    st.session_state.fullscreen_thesis = not st.session_state.fullscreen_thesis
                    st.rerun()
            with nav_col3:
                if st.session_state.chapter_index < len(chapters_list) - 1:
                    st.button("Next Chapter", width="stretch", on_click=go_next)

        except Exception as e:
            st.error(f"Error parsing document: {e}")
    else:
        st.warning("crop_disease_detection.docx not found.")
    st.markdown("</div>", unsafe_allow_html=True)

# --- PAGE 4: PROJECT PRESENTATION SLIDES ---
elif page == "Project Presentation Slides":
    if "fullscreen_slides" not in st.session_state:
        st.session_state.fullscreen_slides = False

    # Inject Fullscreen CSS when enabled
    if st.session_state.fullscreen_slides:
        st.markdown("""
        <style>
        section[data-testid="stSidebar"] {
            display: none !important;
        }
        .main .block-container {
            max-width: 98% !important;
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        header[data-testid="stHeader"] {
            display: none !important;
        }
        footer {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)

    st.markdown("<h1 class='main-title'>Project Presentation Deck</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Interactive presentation deck summarizing technical research, methodology, empirical results, and software implementation.</p>", unsafe_allow_html=True)
    
    slides_list = [
        "1. Title & Team Overview",
        "2. Problem Statement & Research Motivation",
        "3. Research Gaps & Objectives",
        "4. End-to-End System Architecture",
        "5. Triplet Attention Mechanism",
        "6. Experimental Dataset & Augmentation",
        "7. Model Optimization & Mobile Benchmarks",
        "8. Explainable AI via Grad-CAM",
        "9. State-of-the-Art Comparative Analysis",
        "10. System Usability & Future Recommendations"
    ]
    
    if "slide_index" not in st.session_state:
        st.session_state.slide_index = 0
        
    if "slide_selector" not in st.session_state or st.session_state.slide_selector not in slides_list:
        st.session_state.slide_selector = slides_list[st.session_state.slide_index]

    def on_slide_change():
        selected = st.session_state.slide_selector
        st.session_state.slide_index = slides_list.index(selected)

    def prev_slide():
        if st.session_state.slide_index > 0:
            st.session_state.slide_index -= 1
            st.session_state.slide_selector = slides_list[st.session_state.slide_index]

    def next_slide():
        if st.session_state.slide_index < len(slides_list) - 1:
            st.session_state.slide_index += 1
            st.session_state.slide_selector = slides_list[st.session_state.slide_index]

    # Slide Top Navigation Bar
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1, 2.5, 1, 1.2])
    
    with ctrl_col1:
        if st.session_state.slide_index > 0:
            st.button("Previous Slide", width="stretch", on_click=prev_slide)
            
    with ctrl_col2:
        st.selectbox(
            "Jump to Slide:",
            slides_list,
            key="slide_selector",
            on_change=on_slide_change
        )
        
    with ctrl_col3:
        if st.session_state.slide_index < len(slides_list) - 1:
            st.button("Next Slide", width="stretch", on_click=next_slide)

    with ctrl_col4:
        fs_button_label = "Exit Fullscreen" if st.session_state.fullscreen_slides else "Fullscreen Mode"
        if st.button(fs_button_label, width="stretch", key="fullscreen_toggle_btn"):
            st.session_state.fullscreen_slides = not st.session_state.fullscreen_slides
            st.rerun()
            
    # Progress Bar
    progress_val = int(((st.session_state.slide_index + 1) / len(slides_list)) * 100)
    st.progress(progress_val)
    st.markdown(f"<p style='text-align: center; color: #7f8c8d; font-size: 0.85rem;'>Slide {st.session_state.slide_index + 1} of {len(slides_list)}</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    current_slide = slides_list[st.session_state.slide_index]
    media_dir = BASE_DIR / "media"
    
    # --- SLIDE CONTENT CONTAINER ---
    st.markdown("<div class='card' style='min-height: 520px; padding: 30px;'>", unsafe_allow_html=True)
    
    if current_slide == "1. Title & Team Overview":
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1b5e20, #2e7d32); color: white; padding: 30px; border-radius: 16px; margin-bottom: 25px; text-align: center;'>
            <h2 style='color: #ffffff; margin-bottom: 6px; font-weight: 800;'>SUNYANI TECHNICAL UNIVERSITY</h2>
            <h4 style='color: #a5d6a7; margin-top: 0; font-weight: 500;'>FACULTY OF APPLIED SCIENCE AND TECHNOLOGY</h4>
            <h5 style='color: #e8f5e9; margin-top: 0; font-style: italic;'>DEPARTMENT OF COMPUTER SCIENCE</h5>
            <hr style='border: 0; height: 1px; background: rgba(255,255,255,0.3); margin: 20px 0;'>
            <h2 style='color: #ffd54f; font-weight: 800; margin: 0;'>1.1 MOBILE BASED CROP DISEASE DETECTION AND ADVISORY SYSTEM</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### Engineering Team & Academic Supervision")
        s1_c1, s1_c2 = st.columns(2)
        with s1_c1:
            st.markdown("""
            <div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #f57f17; margin-bottom: 15px;'>
                <h4 style='margin:0; color:#1b5e20;'>Ntiamoah Prince Agyei</h4>
                <p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH220135</b></p>
                <span style='display:inline-block; padding:4px 10px; background:#f57f17; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>DevOps & Model Deployment Engineer</span>
            </div>
            <div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #2e7d32; margin-bottom: 15px;'>
                <h4 style='margin:0; color:#1b5e20;'>Adjei Sarfo Joseph</h4>
                <p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH221244</b></p>
                <span style='display:inline-block; padding:4px 10px; background:#2e7d32; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>Lead AI & Machine Learning Researcher</span>
            </div>
            """, unsafe_allow_html=True)
        with s1_c2:
            st.markdown("""
            <div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #388e3c; margin-bottom: 15px;'>
                <h4 style='margin:0; color:#1b5e20;'>Abdul Wasiu Abubakr</h4>
                <p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH220035</b></p>
                <span style='display:inline-block; padding:4px 10px; background:#388e3c; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>Full-Stack & Mobile Software Engineer</span>
            </div>
            <div style='background-color: #f1f8e9; padding: 18px; border-radius: 12px; border-left: 6px solid #43a047; margin-bottom: 15px;'>
                <h4 style='margin:0; color:#1b5e20;'>Lomotey Nathaniel Julian</h4>
                <p style='margin: 4px 0; color:#555;'>Index No: <b>STUBTECH220073</b></p>
                <span style='display:inline-block; padding:4px 10px; background:#43a047; color:white; border-radius:6px; font-size:12px; font-weight:bold;'>Data Engineer & XAI Evaluation Specialist</span>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("""
        <div style='background-color: #fffde7; padding: 16px; border-radius: 12px; border: 2px solid #ffd54f; text-align: center; margin-top: 10px;'>
            <h4 style='margin:0; color:#f57f17;'>Project Supervisor & Academic Advisor</h4>
            <h3 style='margin: 5px 0 0 0; color:#2e7d32;'>Mr. Solomon</h3>
            <p style='margin:2px 0 0 0; color:#666;'>Department of Computer Science, Sunyani Technical University</p>
        </div>
        """, unsafe_allow_html=True)

    elif current_slide == "2. Problem Statement & Research Motivation":
        st.markdown("## Problem Statement & Research Motivation")
        st.markdown("Smallholder farmers in sub-Saharan Africa face up to 40% annual crop yield losses due to unmanaged leaf pathologies (Tomato and Maize diseases). Existing automated diagnosis tools suffer from critical operational limitations:")
        
        prob_c1, prob_c2 = st.columns(2)
        with prob_c1:
            st.markdown("""
            <div style='background:#ffebee; padding:20px; border-radius:12px; border-left:6px solid #e53935; margin-bottom:15px;'>
                <h4 style='color:#c62828; margin:0 0 8px 0;'>1. High Model Storage Footprint</h4>
                <p style='color:#37474f; font-size:14px; margin:0;'>Standard CNN architectures (AlexNet ~200MB, ResNet50 ~100MB) exceed typical low-cost smartphone storage limits in rural agricultural communities.</p>
            </div>
            <div style='background:#ffebee; padding:20px; border-radius:12px; border-left:6px solid #e53935;'>
                <h4 style='color:#c62828; margin:0 0 8px 0;'>2. Cloud Dependency & Mobile Latency</h4>
                <p style='color:#37474f; font-size:14px; margin:0;'>Cloud API reliance requires continuous 3G/4G connectivity. Rural connectivity outages and cellular data costs (1.2–3.4 GB) severely hinder field deployment.</p>
            </div>
            """, unsafe_allow_html=True)
        with prob_c2:
            st.markdown("""
            <div style='background:#ffebee; padding:20px; border-radius:12px; border-left:6px solid #e53935; margin-bottom:15px;'>
                <h4 style='color:#c62828; margin:0 0 8px 0;'>3. Black-Box AI Distrust</h4>
                <p style='color:#37474f; font-size:14px; margin:0;'>Standard deep learning models produce diagnostic class labels without visual explanations, causing extension officers and farmers to distrust AI predictions.</p>
            </div>
            <div style='background:#ffebee; padding:20px; border-radius:12px; border-left:6px solid #e53935;'>
                <h4 style='color:#c62828; margin:0 0 8px 0;'>4. Lack of Actionable Offline Advice</h4>
                <p style='color:#37474f; font-size:14px; margin:0;'>Existing mobile applications output single labels without instant offline access to localized chemical, organic, and cultural treatment measures.</p>
            </div>
            """, unsafe_allow_html=True)

    elif current_slide == "3. Research Gaps & Objectives":
        st.markdown("## Research Gap Fulfillment Matrix")
        st.markdown("Our proposed framework systematically resolves the 5 major research gaps identified in agricultural AI literature:")
        
        st.table([
            {"Identified Research Gap": "Gap 1: High Model Storage Footprint", "Proposed Technical Solution": "Triplet Attention EfficientNet-B0 + INT8 Post-Training Quantization", "Verified Outcome": "COMPLETED: 5.1 MB model size (74.8% reduction), 97.85% accuracy"},
            {"Identified Research Gap": "Gap 2: Cloud Dependency & High Rural Latency", "Proposed Technical Solution": "Native TFLite Mobile Client (Flutter Cross-Platform)", "Verified Outcome": "COMPLETED: 92 ms offline inference on low-cost mobile CPU"},
            {"Identified Research Gap": "Gap 3: Black-Box Model Distrust", "Proposed Technical Solution": "Grad-CAM Attention Heatmap visual overlay", "Verified Outcome": "COMPLETED: Visual lesion validation integrated into diagnostic UI"},
            {"Identified Research Gap": "Gap 4: Lack of Actionable Offline Remedies", "Proposed Technical Solution": "Offline SQLite Local Database (DbService)", "Verified Outcome": "COMPLETED: Instant chemical, organic, and prevention advice"},
            {"Identified Research Gap": "Gap 5: Absence of Integrated End-to-End System", "Proposed Technical Solution": "Flutter Mobile Client + Streamlit Diagnostic Sandbox", "Verified Outcome": "COMPLETED: Full software deployment with 76.5 SUS usability score"}
        ])

    elif current_slide == "4. End-to-End System Architecture":
        st.markdown("## End-to-End Mobile System Architecture")
        arch_c1, arch_c2 = st.columns([1.2, 1])
        with arch_c1:
            st.markdown("""
            <div style='background-color: #f8f9fa; padding: 20px; border-radius: 12px; border: 1px solid #dee2e6;'>
                <h4 style='color: #2c3e50; margin-top:0;'>System Data Flow & Pipeline Steps:</h4>
                <ol style='line-height: 1.8; color: #34495e;'>
                    <li><b>Image Acquisition:</b> Farmer captures leaf photo via smartphone camera or selects from gallery.</li>
                    <li><b>Local Preprocessing:</b> Native resize to 224x224x3 RGB and normalization.</li>
                    <li><b>Offline TFLite Engine:</b> On-device INT8 quantized EfficientNet-B0 model executes inference locally.</li>
                    <li><b>Grad-CAM Explainability:</b> Computes feature map activation heatmap for visual validation.</li>
                    <li><b>Local SQLite DB:</b> Queries offline treatment database for prevention, chemical, and organic remedies.</li>
                    <li><b>Historical Logging:</b> Diagnosis and images logged to local device storage without internet access.</li>
                </ol>
            </div>
            """, unsafe_allow_html=True)
        with arch_c2:
            if (media_dir / "image11.png").exists():
                st.image(str(media_dir / "image11.png"), caption="Figure 3.8: Mobile Application Architecture Diagram", width="stretch")
            elif (media_dir / "image1.png").exists():
                st.image(str(media_dir / "image1.png"), caption="System Design Workflow", width="stretch")

    elif current_slide == "5. Triplet Attention Mechanism":
        st.markdown("## Triplet Attention Mechanism in EfficientNet-B0")
        st.markdown("To maximize disease classification precision across subtle lesion boundaries, we incorporated **Triplet Attention** across the EfficientNet-B0 backbone:")
        
        att_c1, att_c2 = st.columns([1, 1.1])
        with att_c1:
            st.markdown("""
            <div style='background:#f1f8e9; padding:20px; border-radius:12px; border-left:6px solid #2e7d32;'>
                <h4 style='color:#1b5e20; margin-top:0;'>Key Technical Advantages:</h4>
                <ul style='line-height:1.8; color:#333;'>
                    <li><b>Cross-Channel Interaction:</b> Captures inter-channel dependencies without dimensional reduction.</li>
                    <li><b>Spatial Attention:</b> Builds 2D spatial attention weights via Z-pool operations.</li>
                    <li><b>Zero Dimensionality Penalty:</b> Introduces negligible parameter overhead (~0.05%) while boosting feature extraction.</li>
                    <li><b>Precision Focus:</b> Enhances sensitivity to small fungal spot lesions on tomato and maize leaves.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with att_c2:
            if (media_dir / "image4.png").exists():
                st.image(str(media_dir / "image4.png"), caption="Figure 3.4: Triplet Attention Module Architecture", width="stretch")
            elif (media_dir / "image5.png").exists():
                st.image(str(media_dir / "image5.png"), caption="Figure 3.5: Spatial & Channel Attention Flow", width="stretch")

    elif current_slide == "6. Experimental Dataset & Augmentation":
        st.markdown("## Experimental Dataset & Augmentation Pipeline")
        st.markdown("Evaluated on **21,394 leaf images** across 14 plant pathology classes (10 Tomato classes, 4 Maize classes):")
        
        ds_c1, ds_c2 = st.columns(2)
        with ds_c1:
            st.markdown("#### Dataset Class Splits (70% Train / 15% Val / 15% Test)")
            st.table([
                {"Crop": "Tomato", "Classes": "10 Classes (9 diseased, 1 healthy)", "Images": "18,222"},
                {"Crop": "Maize", "Classes": "4 Classes (3 diseased, 1 healthy)", "Images": "3,172"},
                {"Total": "14 Classes", "Split Ratio": "70% / 15% / 15%", "Total Images": "21,394"}
            ])
        with ds_c2:
            st.markdown("#### Data Augmentation Strategy")
            st.table([
                {"Technique": "Rotation", "Parameter": "±30°", "Rationale": "Leaf capture tilt"},
                {"Technique": "Zoom & Shear", "Parameter": "±20% / ±15%", "Rationale": "Distance variation"},
                {"Technique": "Brightness", "Parameter": "[0.7 – 1.3]", "Rationale": "Outdoor light changes"},
                {"Technique": "Flips", "Parameter": "Horizontal & Vertical", "Rationale": "Leaf symmetry"}
            ])

    elif current_slide == "7. Model Optimization & Mobile Benchmarks":
        st.markdown("## Model Quantization & Mobile Benchmarking")
        st.markdown("To enable offline mobile deployment, the trained FP32 Keras model (~20.3 MB) was converted into an **INT8 Quantized TFLite Model (~5.1 MB)**:")
        
        st.table([
            {"Model Variant": "Keras Baseline (FP32)", "Model Size": "20.3 MB", "Test Accuracy": "98.24%", "PC CPU Latency": "42 ms", "Mobile CPU Latency": "310 ms", "Deployment Feasibility": "Server / Cloud"},
            {"Model Variant": "TFLite Quantized (INT8)", "Model Size": "5.1 MB", "Test Accuracy": "97.85%", "PC CPU Latency": "11 ms", "Mobile CPU Latency": "92 ms", "Deployment Feasibility": "Adopted Edge Mobile"}
        ])
        
        m_c1, m_c2, m_c3 = st.columns(3)
        with m_c1:
            st.metric(label="Model Size Reduction", value="74.8%", delta="-15.2 MB")
        with m_c2:
            st.metric(label="Mobile CPU Latency", value="92 ms", delta="-218 ms faster")
        with m_c3:
            st.metric(label="Test Set Accuracy", value="97.85%", delta="-0.39% trade-off")

    elif current_slide == "8. Explainable AI via Grad-CAM":
        st.markdown("## Visual Explainability via Grad-CAM")
        st.markdown("Integrated **Gradient-weighted Class Activation Mapping (Grad-CAM)** to highlight discriminatory spatial regions influencing diagnostic predictions:")
        
        xai_c1, xai_c2 = st.columns([1, 1.2])
        with xai_c1:
            st.markdown("""
            <div style='background:#e8eaf6; padding:20px; border-radius:12px; border-left:6px solid #3f51b5;'>
                <h4 style='color:#1a237e; margin-top:0;'>Benefits of Visual XAI:</h4>
                <ul style='line-height:1.8; color:#2c3e50;'>
                    <li><b>Lesion Localization:</b> Highlights specific leaf spots, rust pustules, and chlorotic patches in red/yellow attention heatmaps.</li>
                    <li><b>User Trust:</b> Allows agricultural extension officers to verify model reasoning rather than relying on black-box labels.</li>
                    <li><b>Misclassification Debugging:</b> Detects background noise bias (e.g. soil or shadow interference).</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with xai_c2:
            if (media_dir / "image9.png").exists():
                st.image(str(media_dir / "image9.png"), caption="Figure 4.3: Grad-CAM Heatmap Activation Map", width="stretch")
            elif (media_dir / "image13.png").exists():
                st.image(str(media_dir / "image13.png"), caption="Mobile App Grad-CAM Diagnostic View", width="stretch")

    elif current_slide == "9. State-of-the-Art Comparative Analysis":
        st.markdown("## State-of-the-Art Literature Comparison")
        st.markdown("Comparing our proposed **Triplet EffNet-B0 + INT8** framework against benchmark published studies in plant pathology:")
        
        st.table([
            {"Study / Reference": "Mohanty et al. (2016) [AlexNet]", "Model Footprint": "~200 MB", "Test Accuracy": "93.50%", "Mobile Latency": "Cloud Only", "XAI Support": "No", "Offline Flutter App": "No"},
            {"Study / Reference": "Too et al. (2019) [DenseNet-121]", "Model Footprint": "~130 MB", "Test Accuracy": "97.20%", "Mobile Latency": "Cloud Only", "XAI Support": "No", "Offline Flutter App": "No"},
            {"Study / Reference": "Agarwal et al. (2021) [MobileNetV2 FP32]", "Model Footprint": "~14 MB", "Test Accuracy": "95.80%", "Mobile Latency": "280 ms", "XAI Support": "No", "Offline Flutter App": "Baseline"},
            {"Study / Reference": "Proposed Framework [Triplet EffNet + INT8]", "Model Footprint": "5.1 MB", "Test Accuracy": "97.85%", "Mobile Latency": "92 ms", "XAI Support": "Yes (Grad-CAM)", "Offline Flutter App": "Yes (Flutter + SQLite)"}
        ])

    elif current_slide == "10. System Usability & Future Recommendations":
        st.markdown("## System Usability, Study Limitations & Future Recommendations")
        
        sus_c1, sus_c2 = st.columns([1.1, 1])
        with sus_c1:
            st.markdown("""
            <div style='background-color: #e8f5e9; padding: 20px; border-radius: 12px; border-left: 6px solid #2e7d32; margin-bottom: 15px;'>
                <h4 style='color: #1b5e20; margin-top:0;'>Usability Evaluation Results:</h4>
                <p style='color: #2c3e50; font-size: 15px;'>Evaluated by <b>15 agricultural extension officers and local farmers</b> using the System Usability Scale (SUS):</p>
                <h2 style='color: #2e7d32; margin: 5px 0;'>SUS Score: 76.5 / 100</h2>
                <span style='background:#2e7d32; color:white; padding:4px 10px; border-radius:6px; font-weight:bold; font-size:12px;'>Grade A: Good to Excellent Usability</span>
            </div>
            
            <div style='background-color: #fff3e0; padding: 18px; border-radius: 12px; border-left: 6px solid #ef6c00; margin-bottom: 15px;'>
                <h4 style='color: #e65100; margin-top:0;'>Study Limitations:</h4>
                <ul style='line-height: 1.5; color: #424242; font-size: 13px;'>
                    <li><b>Crop Scope:</b> Restricted to 14 classes across Tomato & Maize.</li>
                    <li><b>Single Leaf:</b> Optimized for close-up single leaf photographs.</li>
                    <li><b>Lighting Glare:</b> Direct tropical sun reflections can affect feature maps.</li>
                    <li><b>Single Label:</b> Identifies primary dominant disease per image.</li>
                    <li><b>Quantization Trade-off:</b> 0.39% accuracy trade-off for 4x compression & 92ms latency.</li>
                </ul>
            </div>
            
            <div style='background-color: #f8f9fa; padding: 18px; border-radius: 12px; border: 1px solid #dee2e6;'>
                <h4 style='color: #2c3e50; margin-top:0;'>Recommendations for Future Work:</h4>
                <ul style='line-height: 1.5; color: #495057; font-size: 13px;'>
                    <li>Expand dataset coverage to Cassava, Yam, and Cocoa crops in Ghana.</li>
                    <li>Integrate bounding-box object detection (YOLOv8-nano TFLite) for multi-leaf scanning.</li>
                    <li>Add voice-guided local language audio (Twi, Fante, Dagbani) for low-literacy farmers.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with sus_c2:
            if (media_dir / "image12.png").exists():
                st.image(str(media_dir / "image12.png"), caption="Figure 4.4: Flutter Mobile Client Home & Diagnostic UI", width="stretch")
            if (media_dir / "image14.png").exists():
                st.image(str(media_dir / "image14.png"), caption="Figure 4.6: Historical Diagnostic Logs UI", width="stretch")
                
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Bottom Slide Controls
    b_col1, b_col2, b_col3 = st.columns([1, 2, 1])
    with b_col1:
        if st.session_state.slide_index > 0:
            st.button("Previous Slide", key="b_prev", width="stretch", on_click=prev_slide)
    with b_col3:
        if st.session_state.slide_index < len(slides_list) - 1:
            st.button("Next Slide", key="b_next", width="stretch", on_click=next_slide)

# --- PAGE 5: DEFENSE PRACTICE QUIZ & PANEL Q&A ---
elif page == "Defense Practice Quiz":
    st.markdown("<h1 class='main-title'>Thesis Defense Practice & Quiz Hub</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Prepare for your thesis examination with tough panel questions, structured model answers, and an interactive mock quiz.</p>", unsafe_allow_html=True)
    
    quiz_tab1, quiz_tab2, quiz_tab3 = st.tabs(["Panel Q&A Master Repository", "Interactive Mock Defense Quiz", "Group Team Study Guide"])
    
    with quiz_tab1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>Top Defense Questions Panel Might Ask</h3>", unsafe_allow_html=True)
        st.markdown("Review model answers, defense strategies, key empirical numbers, and mathematical justifications categorized by thesis domain.")
        
        cat_filter = st.selectbox(
            "Filter Questions by Domain:",
            [
                "All Categories",
                "1. AI Architecture & Triplet Attention",
                "2. Model Quantization & Edge Mobile Optimization",
                "3. Explainable AI (Grad-CAM) & Model Trust",
                "4. Datasets, Augmentation & Generalization",
                "5. Software Architecture & System Usability (SUS)"
            ]
        )
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Q1
        if cat_filter in ["All Categories", "1. AI Architecture & Triplet Attention"]:
            with st.expander("Q1 [Panel Favorite]: Why EfficientNet-B0 over deeper backbones like ResNet-50 or Vision Transformers (ViT)?"):
                st.markdown("""
                **Difficulty Level**: High Risk  
                **Core Question**: Why did you choose EfficientNet-B0 instead of ResNet-50, VGG-16, or Vision Transformers?
                
                #### Model Defense Answer:
                > *"EfficientNet-B0 uses compound scaling to uniformly scale network depth ($d$), width ($w$), and image resolution ($r$) using a fixed ratio: $d \\cdot w^2 \\cdot r^2 \\approx 2$. ResNet-50 has 25.6 million parameters (~98 MB FP32), and VGG-16 has 138 million parameters (~500 MB), whereas EfficientNet-B0 has only 5.3 million parameters (~20.3 MB FP32).*
                > 
                > *Because our primary deployment target is **offline execution on budget Android smartphones in low-connectivity agricultural areas**, EfficientNet-B0 provides an optimal trade-off: high spatial feature representation per parameter with 4.7x fewer parameters than ResNet-50, preventing memory crashes during TFLite initialization."*
                
                **Key Numbers to Quote**:
                - EfficientNet-B0 FP32 size: **20.3 MB** (5.3M parameters)
                - ResNet-50 size: **98 MB** (25.6M parameters)
                - Baseline Accuracy: **98.24%**
                """)
                
        # Q2
        if cat_filter in ["All Categories", "1. AI Architecture & Triplet Attention"]:
            with st.expander("Q2 [Panel Favorite]: How does Triplet Attention work, and why is it superior to SE or CBAM?"):
                st.markdown("""
                **Difficulty Level**: High Risk  
                **Core Question**: What is the Triplet Attention Mechanism, and why not use Squeeze-and-Excitation (SE) or CBAM?
                
                #### Model Defense Answer:
                > *"Standard Squeeze-and-Excitation (SE) attention computes only channel attention via global average pooling. CBAM computes channel and spatial attention sequentially, but relies on heavy channel dimensionality reduction ($C/r$) which loses fine-grained spatial information.*
                > 
                > *Triplet Attention captures cross-dimension interactions without any dimensionality reduction using three parallel branches:*
                > 1. *Branch 1: Rotates input tensor to $(H, C, W)$ to capture $(C, H)$ spatial-channel interaction.*
                > 2. *Branch 2: Rotates input tensor to $(W, H, C)$ to capture $(C, W)$ spatial-channel interaction.*
                > 3. *Branch 3: Standard spatial attention $(H, W)$ via 7x7 convolution.*
                > 
                > *Outputs are averaged, preserving fine-grained leaf pathology structures (rust pustules, chlorotic spots) with zero channel bottlenecks and only a negligible parameter addition (+0.05M params)."*
                
                **Key Math / Formula**:
                - Triplet Output: $y = \\frac{1}{3} \\left( \\hat{\\chi}_1 + \\hat{\\chi}_2 + \\hat{\\chi}_3 \\right)$
                """)

        # Q3
        if cat_filter in ["All Categories", "1. AI Architecture & Triplet Attention"]:
            with st.expander("Q3: Why use a 2-Phase Transfer Learning strategy instead of end-to-end training from epoch 1?"):
                st.markdown("""
                **Difficulty Level**: Medium  
                **Core Question**: Why split training into two phases?
                
                #### Model Defense Answer:
                > *"Training from scratch on 21,394 images risks overfitting or gradient explosion because the classification head weights are randomly initialized.*
                > 
                > *In **Phase 1**, we freeze the ImageNet-pretrained EfficientNet backbone and train only the newly attached dense classification head at a higher learning rate ($\\eta = 10^{-3}$) for 5 epochs to reach stability.*
                > *In **Phase 2**, we unfreeze the top MBConv blocks and fine-tune the entire network at a low learning rate ($\\eta = 10^{-5}$) for 15 epochs. This prevents 'catastrophic forgetting' of general edge/texture visual primitives while specializing upper layers to plant lesion patterns."*
                """)

        # Q4
        if cat_filter in ["All Categories", "2. Model Quantization & Edge Mobile Optimization"]:
            with st.expander("Q4 [Panel Favorite]: Why Post-Training INT8 Quantization (PTQ) over Quantization-Aware Training (QAT)?"):
                st.markdown("""
                **Difficulty Level**: High Risk  
                **Core Question**: Explain your quantization choice and trade-off metrics.
                
                #### Model Defense Answer:
                > *"Post-Training Quantization (PTQ) converts 32-bit floating point weights ($W_{fp32}$) and activations ($X_{fp32}$) into 8-bit signed integers ($W_{int8}, X_{int8}$) using a representative calibration dataset ($N=100$ unaugmented validation images).*
                > 
                > *PTQ achieved a **74.8% memory compression ratio** (reducing model size from 20.3 MB down to 5.1 MB) and dropped CPU inference latency from **310 ms to 92 ms** on mobile hardware, while incurring only a minor **0.39% accuracy trade-off** (98.24% FP32 vs 97.85% INT8).*
                > 
                > *Because accuracy remained at 97.85%, complex Quantization-Aware Training (QAT)—which requires retraining with fake-quantization nodes—was unnecessary."*
                
                **Key Quantization Formula**:
                - $r = S \\cdot (q - Z)$
                - Scale $S = \\frac{r_{\\max} - r_{\\min}}{q_{\\max} - q_{\\min}}$, Zero Point $Z = \\text{round}\\left(-\\frac{r_{\\min}}{S}\\right) - 128$
                """)

        # Q5
        if cat_filter in ["All Categories", "2. Model Quantization & Edge Mobile Optimization"]:
            with st.expander("Q5: How does your system guarantee 100% offline functionality in low-connectivity rural farms?"):
                st.markdown("""
                **Difficulty Level**: Medium  
                **Core Question**: Does your mobile app require internet or cloud servers to run diagnostics?
                
                #### Model Defense Answer:
                > *"No cloud server or internet connection is required. The 5.1 MB quantized TFLite model (`plant_disease_model.tflite`) is compiled directly into the Flutter application assets bundle.*
                > 
                > *Inference is executed locally on-device using the `tflite_flutter` C++ plugin binding (`libtensorflowlite_c.so` / `.dll`). Historical diagnostic records, treatment recommendations, and farmer activity logs are stored locally in an embedded SQLite database (`sqflite`). This eliminates data subscription costs ($1.20–$3.40/month saved per farmer) and latency spikes."*
                """)

        # Q6
        if cat_filter in ["All Categories", "3. Explainable AI (Grad-CAM) & Model Trust"]:
            with st.expander("Q6 [Panel Favorite]: How does Grad-CAM work, and why is XAI critical in agricultural AI?"):
                st.markdown("""
                **Difficulty Level**: High Risk  
                **Core Question**: Explain Grad-CAM mathematically and justify its necessity for farmers.
                
                #### Model Defense Answer:
                > *"Grad-CAM computes the gradient of the predicted score $y^c$ for class $c$ with respect to feature activation maps $A^k$ of the final convolutional layer:*
                > 
                > $$\\alpha_k^c = \\frac{1}{Z} \\sum_i \\sum_j \\frac{\\partial y^c}{\\partial A_{i,j}^k}$$
                > 
                > *A weighted combination is passed through a ReLU activation: $L_{\\text{Grad-CAM}}^c = \\text{ReLU}\\left(\\sum_k \\alpha_k^c A^k\\right)$.*
                > 
                > *XAI is critical because agricultural extension officers and farmers distrust black-box labels. Grad-CAM visual heatmaps prove that the neural network focuses on actual chlorotic leaf spots and rust pustules rather than background noise like soil, shadows, or human hands."*
                """)

        # Q7
        if cat_filter in ["All Categories", "4. Datasets, Augmentation & Generalization"]:
            with st.expander("Q7: How did you prevent data leakage and handle class imbalance across 21,394 images?"):
                st.markdown("""
                **Difficulty Level**: Medium  
                **Core Question**: How did you split the dataset and handle class imbalance?
                
                #### Model Defense Answer:
                > *"We used an **80-10-10 stratified random split** (17,115 train, 2,139 val, 2,140 test) preserving class distributions across all 14 crop pathology categories.*
                > 
                > *To prevent data leakage, data augmentations (random rotation ±20°, horizontal/vertical flip, brightness jitter ±15%, zoom ±10%) were applied **strictly to training batches dynamically in memory**. Test and validation sets were kept 100% clean and unaugmented.*
                > *Class imbalance was mitigated using class-weighted categorical cross-entropy loss weights: $w_j = \\frac{N}{K \\cdot n_j}$."*
                """)

        # Q8
        if cat_filter in ["All Categories", "4. Datasets, Augmentation & Generalization"]:
            with st.expander("Q8: What happens when a farmer scans an out-of-distribution (OOD) image (e.g. Cassava, Cocoa, or non-leaf)?"):
                st.markdown("""
                **Difficulty Level**: High Risk  
                **Core Question**: How does the system handle non-supported crops or background photos?
                
                #### Model Defense Answer:
                > *"As documented in Section 1.5 and Section 5.3 (Limitations of the Study), our model is trained on a closed set of 14 categories across Tomato and Maize.*
                > 
                > *To mitigate Out-of-Distribution (OOD) misclassifications, the diagnostic engine implements a **softmax confidence threshold $\\tau = 0.65$**. If $\\max(P(y|x)) < 0.65$, the system triggers an 'Uncertain / Off-Target Input' alert advising the user to reposition the camera over a clean single leaf against a clear background."*
                """)

        # Q9
        if cat_filter in ["All Categories", "5. Software Architecture & System Usability (SUS)"]:
            with st.expander("Q9: Explain your System Usability Scale (SUS) evaluation methodology and results."):
                st.markdown("""
                **Difficulty Level**: Medium  
                **Core Question**: How did you measure user usability and what does your SUS score mean?
                
                #### Model Defense Answer:
                > *"We conducted a field usability trial with **15 participants** (10 smallholder farmers and 5 agricultural extension officers).*
                > 
                > *Using John Brooke's (1996) standard 10-item Likert-scale questionnaire (1 = Strongly Disagree, 5 = Strongly Agree), positive item scores were computed as $(x_i - 1)$ and negative item scores as $(5 - x_i)$. The total sum was multiplied by 2.5.*
                > 
                > *Our system achieved a **mean SUS score of 76.5 / 100**, which corresponds to **Grade A ('Good to Excellent Usability')** on Bangor et al. (2008) acceptability scales."*
                """)

        # Q10
        if cat_filter in ["All Categories", "5. Software Architecture & System Usability (SUS)"]:
            with st.expander("Q10: What are the main contributions of your research to Computer Science and Agriculture?"):
                st.markdown("""
                **Difficulty Level**: Medium  
                **Core Question**: Summarize your core research contributions.
                
                #### Model Defense Answer:
                > *"Our research delivers three primary technical contributions:*
                > 1. ***Architectural Innovation***: First integration of Triplet Attention with EfficientNet-B0 for sub-10MB mobile crop pathology diagnosis with 97.85% INT8 accuracy.
                > 2. ***Explainability & Trust***: On-device Grad-CAM heatmap visualization ensuring transparent AI reasoning for non-technical farmers.
                > 3. ***Production Mobile Engineering***: A fully offline, cross-platform Flutter application with local SQLite database schema and instant 92 ms execution."*
                """)

    with quiz_tab2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>Interactive Mock Defense Quiz</h3>", unsafe_allow_html=True)
        st.markdown("Test your readiness for panel questioning. Answer all 5 questions below and check your score!")
        
        quiz_q1 = st.radio(
            "1. What is the parameter count and FP32 model size of EfficientNet-B0?",
            [
                "A) 25.6M parameters (~98 MB)",
                "B) 5.3M parameters (~20.3 MB)",
                "C) 138M parameters (~500 MB)",
                "D) 1.2M parameters (~4.5 MB)"
            ],
            key="quiz_q1"
        )
        
        quiz_q2 = st.radio(
            "2. How does Triplet Attention avoid losing spatial fine-grained features during channel processing?",
            [
                "A) By applying heavy channel reduction (C/r = 16)",
                "B) By capturing cross-dimension interactions across (C,H), (C,W), and (H,W) without channel dimensionality reduction",
                "C) By ignoring spatial attention and computing only global average pooling",
                "D) By using 1x1 depthwise separable max pooling"
            ],
            key="quiz_q2"
        )
        
        quiz_q3 = st.radio(
            "3. What model size and latency were achieved after INT8 Post-Training Quantization?",
            [
                "A) 15.2 MB size and 250 ms latency",
                "B) 5.1 MB size and 92 ms latency",
                "C) 1.5 MB size and 15 ms latency",
                "D) 20.3 MB size and 310 ms latency"
            ],
            key="quiz_q3"
        )
        
        quiz_q4 = st.radio(
            "4. What mathematical layer is used at the end of Grad-CAM to ensure only positive feature activations are visualised?",
            [
                "A) Softmax",
                "B) Sigmoid",
                "C) ReLU",
                "D) LeakyReLU"
            ],
            key="quiz_q4"
        )
        
        quiz_q5 = st.radio(
            "5. What System Usability Scale (SUS) score and Grade did the mobile app achieve during field testing?",
            [
                "A) 62.5 / 100 (Grade C - Marginal)",
                "B) 76.5 / 100 (Grade A - Good to Excellent)",
                "C) 88.0 / 100 (Grade A+ - Best Possible)",
                "D) 50.0 / 100 (Grade F - Poor)"
            ],
            key="quiz_q5"
        )
        
        if st.button("Submit Practice Quiz", key="submit_quiz_btn"):
            score = 0
            if quiz_q1.startswith("B"): score += 1
            if quiz_q2.startswith("B"): score += 1
            if quiz_q3.startswith("B"): score += 1
            if quiz_q4.startswith("C"): score += 1
            if quiz_q5.startswith("B"): score += 1
            
            percent = (score / 5) * 100
            
            st.markdown("<hr>", unsafe_allow_html=True)
            if percent >= 80:
                st.balloons()
                st.success(f"🎉 **Defense Readiness Score: {score}/5 ({percent:.0f}%) — Excellent! You are fully prepared for panel questioning.**")
            elif percent >= 60:
                st.warning(f"👍 **Defense Readiness Score: {score}/5 ({percent:.0f}%) — Good job! Review the panel Q&A answers above to polish your defense.**")
            else:
                st.error(f"📚 **Defense Readiness Score: {score}/5 ({percent:.0f}%) — Needs Review. Study the Master Q&A Repository tab before defense.**")
                
        st.markdown("</div>", unsafe_allow_html=True)

    with quiz_tab3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>Group Member Study Guide & Key Terms Panel</h3>", unsafe_allow_html=True)
        st.markdown("Use this comprehensive guide to align all 4 project members before your final presentation.")
        
        st.markdown("#### 1. Executive Summary (What We Built)")
        st.markdown("""
        Our project solves a critical agricultural problem in Ghana: **smallholder tomato and maize farmers lose up to 40% of crop yields to diseases (e.g. Early Blight, Late Blight, Northern Leaf Blight, Rust)** because traditional expert diagnosis is slow, expensive, and requires internet access that rural farms lack.
        
        We built an **offline-first AI mobile application** using a novel **Triplet Attention-Enhanced EfficientNet-B0 architecture**. The system is quantized to **5.1 MB**, runs in **92 ms** on budget smartphones without internet, provides **Grad-CAM visual heatmaps** to explain predictions, and achieved a **76.5 (Grade A) System Usability Scale (SUS)** rating during field testing.
        """)
        
        st.markdown("#### 2. Key Terms & Acronyms Dictionary")
        st.markdown("""
        | Term / Acronym | Full Name | Plain English Definition |
        |---|---|---|
        | **CNN** | Convolutional Neural Network | A deep learning model specialized for processing grid-like visual data (images). |
        | **EfficientNet-B0** | Efficient Network (Base Version) | A lightweight CNN backbone that uniformly scales depth, width, and resolution using compound scaling. |
        | **Triplet Attention** | Triplet Attention Mechanism | A zero-parameter-reduction attention module that captures spatial-channel interactions across 3 parallel tensor dimensions. |
        | **Transfer Learning** | Pre-trained Weight Adaptation | A technique where a model pre-trained on 1.4 million ImageNet photos is fine-tuned on our 21,394 plant leaf images. |
        | **PTQ INT8** | Post-Training INT8 Quantization | A compression technique that converts 32-bit floating point weights into 8-bit integers, shrinking model size by 74.8%. |
        | **TFLite** | TensorFlow Lite | A lightweight runtime engine used to execute AI models directly on mobile devices (Android/iOS). |
        | **Grad-CAM** | Gradient-weighted Class Activation Mapping | An Explainable AI (XAI) technique that generates visual color heatmaps showing where the AI focused on the leaf. |
        | **XAI** | Explainable Artificial Intelligence | Methods that make AI decisions transparent, understandable, and trustworthy for non-expert human users. |
        | **SUS** | System Usability Scale | A standardized 10-item Likert survey used to quantify software usability (0-100 scale). |
        | **SQLite** | Structured Query Language Lite | A self-contained, serverless database engine embedded inside the Flutter app for offline history logging. |
        """)
        
        st.markdown("#### 3. Core Technical Methods Explained")
        
        with st.expander("Method 1: EfficientNet-B0 Compound Scaling"):
            st.markdown("""
            - **What it is**: Traditional CNNs scale depth ($d$), width ($w$), or resolution ($r$) arbitrarily. EfficientNet uses a compound coefficient $\\phi$ where:
              $$\\text{Depth } d = \\alpha^\\phi, \\quad \\text{Width } w = \\beta^\\phi, \\quad \\text{Resolution } r = \\gamma^\\phi$$
              subject to $\\alpha \\cdot \\beta^2 \\cdot \\gamma^2 \\approx 2$.
            - **Why we used it**: It achieves 98.24% baseline accuracy with only **5.3 million parameters (20.3 MB FP32)**, compared to ResNet-50 which requires 25.6M parameters (98 MB).
            """)
            
        with st.expander("Method 2: Triplet Attention Module"):
            st.markdown("""
            - **What it is**: It uses 3 parallel branches to capture dependencies across tensor dimensions:
              1. **Branch 1**: $(C, H)$ spatial-channel interaction.
              2. **Branch 2**: $(C, W)$ spatial-channel interaction.
              3. **Branch 3**: $(H, W)$ spatial attention.
            - **Why we used it**: Squeeze-and-Excitation (SE) attention discards spatial details via global pooling. Triplet Attention preserves fine-grained lesion spots (pustules, chlorosis) without channel bottleneck loss.
            """)

        with st.expander("Method 3: 2-Phase Transfer Learning"):
            st.markdown("""
            - **Phase 1 (Head Training)**: Freeze backbone, train custom classifier head for 5 epochs at $\\eta = 10^{-3}$.
            - **Phase 2 (Fine-Tuning)**: Unfreeze top MBConv blocks, fine-tune end-to-end for 15 epochs at $\\eta = 10^{-5}$.
            - **Why we used it**: Prevents catastrophic forgetting of low-level visual edges while adapting high-level features to tomato and maize pathologies.
            """)

        with st.expander("Method 4: INT8 Post-Training Quantization (PTQ)"):
            st.markdown("""
            - **What it is**: Converts 32-bit floats to 8-bit signed integers: $r = S \\cdot (q - Z)$.
            - **Why we used it**: Reduces model size by **74.8% (20.3 MB $\\to$ 5.1 MB)** and latency by **70.3% (310 ms $\\to$ 92 ms)** while retaining **97.85% accuracy** (only 0.39% trade-off).
            """)

        with st.expander("Method 5: Grad-CAM Visual Explainability"):
            st.markdown("""
            - **What it is**: Computes gradient weights $\\alpha_k^c = \\frac{1}{Z} \\sum \\frac{\\partial y^c}{\\partial A^k}$ and generates heatmap $L^c = \\text{ReLU}(\\sum \\alpha_k^c A^k)$.
            - **Why we used it**: Proves the model targets actual leaf lesions rather than background noise (soil, shadows, hands), building trust with agricultural officers.
            """)

        st.markdown("#### 4. Master Numbers to Memorize")
        st.markdown("""
        | Metric | Value | Meaning / Context |
        |---|---|---|
        | **Dataset Size** | **21,394 images** | 14 classes across Tomato (10) and Maize (4). |
        | **Dataset Split** | **80% / 10% / 10%** | Stratified split: 17,115 train, 2,139 val, 2,140 test. |
        | **FP32 Accuracy** | **98.24%** | Unquantized full model accuracy (20.3 MB). |
        | **INT8 Accuracy** | **97.85%** | Quantized model accuracy (5.1 MB). |
        | **Compression Ratio**| **74.8%** | Size reduction from 20.3 MB to 5.1 MB. |
        | **Mobile Latency** | **92 ms** | Execution time on mobile CPU (down from 310 ms). |
        | **SUS Score** | **76.5 / 100** | Grade A ("Good to Excellent") field usability score. |
        | **Participants** | **15 participants** | 10 smallholder farmers + 5 extension officers. |
        """)
        
        st.markdown("#### 5. Team Member Role Responsibilities")
        st.markdown("""
        * **Ntiamoah Prince Agyei** *(DevOps & Model Deployment Engineer)*:
          * **Focus**: TFLite export, INT8 quantization benchmarks, Streamlit Cloud deployment, mobile CPU latency optimization.
        * **Adjei Sarfo Joseph** *(Lead AI & Machine Learning Researcher)*:
          * **Focus**: EfficientNet-B0 backbone, Triplet Attention equations, 2-phase learning rate schedules, accuracy loss curves.
        * **Abdul Wasiu Abubakr** *(Full-Stack & Mobile Software Engineer)*:
          * **Focus**: Flutter application UI screens, `tflite_flutter` C++ dynamic binding, embedded SQLite (`sqflite`) database logging.
        * **Lomotey Nathaniel Julian** *(Data Engineer & XAI Evaluation Specialist)*:
          * **Focus**: Dataset preprocessing/augmentation, Grad-CAM heatmap generation, confusion matrices, System Usability Scale (SUS) survey analysis.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

# --- PAGE 6: SUS USABILITY SURVEY & LIVE ANALYTICS ---
elif page == "SUS Usability Survey & Analytics":
    st.markdown("<h1 class='main-title'>System Usability Scale (SUS) Survey & Live Analytics</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Gather real participant usability feedback using John Brooke's (1996) standard 10-item instrument and analyze real-time evaluation metrics.</p>", unsafe_allow_html=True)
    
    sus_csv_path = BASE_DIR / "sus_responses.csv"
    
    sus_tab1, sus_tab2 = st.tabs(["Submit New SUS Response", "Live Analytics & Visual Dashboard"])
    
    with sus_tab1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>Participant Information</h3>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            p_id = st.text_input("Participant ID / Name:", value=f"P{datetime.now().strftime('%M%S')}")
        with c2:
            p_role = st.selectbox("Role / Occupation:", ["Smallholder Farmer", "Extension Officer", "Researcher / Academic", "Student"])
        with c3:
            p_exp = st.selectbox("Software Experience Level:", ["Beginner", "Intermediate", "Expert"])
            
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<h3>John Brooke (1996) 10-Item Likert Questionnaire</h3>", unsafe_allow_html=True)
        st.markdown("Please rate your agreement with each statement from **1 (Strongly Disagree)** to **5 (Strongly Agree)**.")
        
        likert_opts = [1, 2, 3, 4, 5]
        
        sq1 = st.radio("1. I think that I would like to use this system frequently.", likert_opts, index=3, horizontal=True, key="sq1")
        sq2 = st.radio("2. I found the system unnecessarily complex.", likert_opts, index=1, horizontal=True, key="sq2")
        sq3 = st.radio("3. I thought the system was easy to use.", likert_opts, index=3, horizontal=True, key="sq3")
        sq4 = st.radio("4. I think that I would need the support of a technical person to be able to use this system.", likert_opts, index=1, horizontal=True, key="sq4")
        sq5 = st.radio("5. I found the various functions in this system were well integrated.", likert_opts, index=3, horizontal=True, key="sq5")
        sq6 = st.radio("6. I thought there was too much inconsistency in this system.", likert_opts, index=1, horizontal=True, key="sq6")
        sq7 = st.radio("7. I would imagine that most people would learn to use this system very quickly.", likert_opts, index=3, horizontal=True, key="sq7")
        sq8 = st.radio("8. I found the system very cumbersome to use.", likert_opts, index=1, horizontal=True, key="sq8")
        sq9 = st.radio("9. I felt very confident using the system.", likert_opts, index=3, horizontal=True, key="sq9")
        sq10 = st.radio("10. I needed to learn a lot of things before I could get going with this system.", likert_opts, index=1, horizontal=True, key="sq10")
        
        if st.button("Calculate & Submit SUS Response", key="submit_sus_btn"):
            # Compute Brooke (1996) SUS Score
            # Odd items: score - 1
            # Even items: 5 - score
            odd_sum = (sq1 - 1) + (sq3 - 1) + (sq5 - 1) + (sq7 - 1) + (sq9 - 1)
            even_sum = (5 - sq2) + (5 - sq4) + (5 - sq6) + (5 - sq8) + (5 - sq10)
            calculated_sus = (odd_sum + even_sum) * 2.5
            
            # Determine Bangor et al. (2008) Grade
            if calculated_sus >= 84.1:
                grade = "Grade A+ (Best Imaginable)"
            elif calculated_sus >= 80.3:
                grade = "Grade A (Excellent)"
            elif calculated_sus >= 68.0:
                grade = "Grade B / A- (Good)"
            elif calculated_sus >= 51.0:
                grade = "Grade C / D (Fair)"
            else:
                grade = "Grade F (Poor)"
                
            # Append to CSV
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = {
                "participant_id": p_id,
                "role": p_role,
                "experience": p_exp,
                "q1": sq1, "q2": sq2, "q3": sq3, "q4": sq4, "q5": sq5,
                "q6": sq6, "q7": sq7, "q8": sq8, "q9": sq9, "q10": sq10,
                "sus_score": calculated_sus,
                "timestamp": now_str
            }
            
            import pandas as pd
            if sus_csv_path.exists():
                df_sus = pd.read_csv(sus_csv_path)
                df_sus = pd.concat([df_sus, pd.DataFrame([new_row])], ignore_index=True)
            else:
                df_sus = pd.DataFrame([new_row])
                
            df_sus.to_csv(sus_csv_path, index=False)
            
            st.balloons()
            st.markdown(f"""
            <div style='background-color: #e8f5e9; border-left: 6px solid #2e7d32; padding: 20px; border-radius: 12px; margin-top: 15px;'>
                <h3 style='color: #1b5e20; margin: 0;'>Response Recorded Successfully!</h3>
                <h1 style='color: #2e7d32; margin: 5px 0;'>SUS Score: {calculated_sus:.1f} / 100</h1>
                <span style='background:#2e7d32; color:white; padding:4px 12px; border-radius:6px; font-weight:bold;'>{grade}</span>
                <p style='margin-top: 10px; color: #555;'>Participant ID: <b>{p_id}</b> | Role: <b>{p_role}</b> | Time: <b>{now_str}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)
        
    with sus_tab2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3>Real Live Data Analytics & Usability Metrics</h3>", unsafe_allow_html=True)
        
        import pandas as pd
        if sus_csv_path.exists():
            df_live = pd.read_csv(sus_csv_path)
            
            if not df_live.empty:
                avg_score = df_live["sus_score"].mean()
                total_n = len(df_live)
                max_score = df_live["sus_score"].max()
                min_score = df_live["sus_score"].min()
                
                # Overall Grade
                if avg_score >= 84.1: overall_grade = "Grade A+"
                elif avg_score >= 80.3: overall_grade = "Grade A"
                elif avg_score >= 68.0: overall_grade = "Grade B / A-"
                elif avg_score >= 51.0: overall_grade = "Grade C"
                else: overall_grade = "Grade F"
                
                # Top KPI Cards
                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    st.metric("Total Responses", f"{total_n}")
                with k2:
                    st.metric("Mean SUS Score", f"{avg_score:.1f} / 100")
                with k3:
                    st.metric("Bangor Usability Grade", overall_grade)
                with k4:
                    st.metric("Score Range", f"{min_score:.0f} - {max_score:.0f}")
                    
                st.markdown("<hr>", unsafe_allow_html=True)
                
                # Visual Charts
                col_ch1, col_ch2 = st.columns(2)
                
                with col_ch1:
                    st.markdown("#### SUS Score Distribution Histogram")
                    fig, ax = plt.subplots(figsize=(6, 4))
                    sns.histplot(df_live["sus_score"], kde=True, bins=8, color="#2e7d32", ax=ax)
                    ax.axvline(avg_score, color="#e74c3c", linestyle="--", linewidth=2, label=f"Mean: {avg_score:.1f}")
                    ax.set_xlabel("SUS Score (0 - 100)")
                    ax.set_ylabel("Participant Count")
                    ax.legend()
                    st.pyplot(fig)
                    plt.close(fig)
                    
                with col_ch2:
                    st.markdown("#### Mean SUS Score by User Role")
                    role_grp = df_live.groupby("role")["sus_score"].mean().reset_index()
                    fig, ax = plt.subplots(figsize=(6, 4))
                    sns.barplot(data=role_grp, x="role", y="sus_score", palette="Greens_d", ax=ax)
                    ax.set_ylim(0, 100)
                    ax.set_ylabel("Mean SUS Score")
                    ax.set_xlabel("Participant Role")
                    for p in ax.patches:
                        ax.annotate(f"{p.get_height():.1f}", (p.get_x() + p.get_width() / 2., p.get_height() - 8),
                                    ha='center', va='center', color='white', fontweight='bold')
                    st.pyplot(fig)
                    plt.close(fig)
                    
                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown("#### Item-by-Item (Q1 - Q10) Likert Means")
                q_cols = [f"q{i}" for i in range(1, 11)]
                q_means = df_live[q_cols].mean()
                
                q_labels = [
                    "Q1: Want frequent use", "Q2: Complex", "Q3: Easy to use", "Q4: Tech support needed",
                    "Q5: Functions integrated", "Q6: Inconsistent", "Q7: Quick to learn", "Q8: Cumbersome",
                    "Q9: Confident using", "Q10: Much learning needed"
                ]
                
                fig, ax = plt.subplots(figsize=(10, 4.5))
                bars = ax.barh(q_labels, q_means.values, color=["#2e7d32" if i%2==0 else "#e65100" for i in range(10)])
                ax.set_xlim(1, 5)
                ax.set_xlabel("Mean Likert Score (1 = Strongly Disagree, 5 = Strongly Agree)")
                for bar in bars:
                    w = bar.get_width()
                    ax.text(w + 0.05, bar.get_y() + bar.get_height()/2, f"{w:.2f}", va='center', fontweight='bold')
                st.pyplot(fig)
                plt.close(fig)
                
                st.markdown("<hr>", unsafe_allow_html=True)
                st.markdown("#### Live Submissions Data Table")
                st.dataframe(df_live, use_container_width=True)
                
                csv_data = df_live.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export All Live SUS Data (.csv)",
                    data=csv_data,
                    file_name="sus_live_evaluation_data.csv",
                    mime="text/csv"
                )
            else:
                st.info("No SUS responses collected yet. Use Tab 1 to submit responses.")
        else:
            st.info("No responses file found. Submit a response in Tab 1 to initialize dataset.")
            
        st.markdown("</div>", unsafe_allow_html=True)
