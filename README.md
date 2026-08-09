# 🌿 Mobile-Based Crop Disease Detection and Advisory System

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)](https://tensorflow.org/)
[![Flutter](https://img.shields.io/badge/Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white)](https://flutter.dev/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)

An intelligent, offline-capable, cross-platform mobile application and deep learning diagnostic system for automated crop disease detection, focusing on economically vital **Tomato (*Solanum lycopersicum*)** and **Maize (*Zea mays*)** crops.

Developed for **Sunyani Technical University** (Faculty of Applied Science and Technology, Department of Computer Science).

---

## 📌 Key Architectural Highlights

* **Deep Learning Backbone**: EfficientNet-B0 augmented with a **Triplet Attention Mechanism** for fine-grained spatial and channel feature extraction across 14 disease and healthy categories.
* **Post-Training INT8 Quantization**: Compressed model footprint from **20.3 MB down to 5.1 MB** (74.8% reduction) with a fast **92 ms mobile CPU inference latency** and **97.85% test accuracy**.
* **Visual Explainability (XAI)**: Integrated **Gradient-weighted Class Activation Mapping (Grad-CAM)** attention heatmaps to provide visual diagnostic proof for farmers and extension officers.
* **Offline Autonomy**: Embedded local **SQLite database** supplying immediate chemical, organic, and preventive treatment guidance with zero network reliance.
* **Dual-Platform Architecture**: Production **Flutter Mobile Application** + Interactive **Streamlit Research & Evaluation Sandbox**.

---

## 👥 Project Team & Engineering Roles

| Contributor | Index Number | Role |
| :--- | :---: | :--- |
| **Ntiamoah Prince Agyei** | `STUBTECH220135` | DevOps & Model Deployment Engineer |
| **Adjei Sarfo Joseph** | `STUBTECH221244` | Lead AI & Machine Learning Researcher |
| **Abdul Wasiu Abubakr** | `STUBTECH220035` | Full-Stack & Mobile Software Engineer |
| **Lomotey Nathaniel Julian** | `STUBTECH220073` | Data Engineer & XAI Evaluation Specialist |

**Academic Supervisor & Project Advisor**: Mr. Solomon *(Department of Computer Science, Sunyani Technical University)*

---

## 🚀 Quickstart Guide (Local Execution)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd YOUR_REPO_NAME
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Streamlit Sandbox App**:
   ```bash
   streamlit run app.py
   ```

---

## ☁️ Deploying to Streamlit Cloud

1. Push this repository to your GitHub account.
2. Sign in to [share.streamlit.io](https://share.streamlit.io/).
3. Click **New App** $\rightarrow$ Select your GitHub repository, branch (`main`), and set Main file path to `app.py`.
4. Click **Deploy!**

---

## 📊 Benchmark Metrics Summary

* **Baseline FP32 Test Accuracy**: `98.24%`
* **INT8 Quantized Test Accuracy**: `97.85%`
* **Model Size**: `5.1 MB`
* **Mobile CPU Latency**: `92 ms`
* **System Usability Scale (SUS) Rating**: `76.5 / 100` *(Grade B 'Good')*
