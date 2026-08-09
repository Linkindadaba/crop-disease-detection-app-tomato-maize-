import 'dart:io';
import 'dart:math';
import 'package:flutter/services.dart';
import 'package:flutter/foundation.dart';
import 'package:image/image.dart' as img;
import 'package:tflite_flutter/tflite_flutter.dart';

class TfliteService {
  static Interpreter? _interpreter;
  static List<String>? _labels;

  static bool get isInitialized => _interpreter != null && _labels != null;

  static Future<void> init() async {
    if (Platform.environment.containsKey('FLUTTER_TEST')) {
      _labels = ['Tomato___healthy', 'Corn_(maize)___healthy'];
      return;
    }
    if (isInitialized) return;

    try {
      // 1. Load Model Buffer dynamically
      final byteData = await rootBundle.load(
        'assets/model/plant_disease_model.tflite',
      );
      final buffer = byteData.buffer.asUint8List(
        byteData.offsetInBytes,
        byteData.lengthInBytes,
      );
      _interpreter = Interpreter.fromBuffer(buffer);
      debugPrint("TFLite Model loaded successfully.");

      // 2. Load Labels
      final labelsString = await rootBundle.loadString(
        'assets/model/labels.txt',
      );
      _labels = labelsString
          .split('\n')
          .map((line) => line.trim())
          .where((line) => line.isNotEmpty)
          .toList();
      debugPrint("TFLite Labels loaded: ${_labels!.length} classes.");
    } catch (e) {
      debugPrint("Error initializing TFLite Service: $e");
    }
  }

  static Future<Map<String, dynamic>> runInference(String imagePath) async {
    if (!isInitialized) {
      await init();
    }

    if (!isInitialized) {
      throw Exception("TfliteService not initialized properly.");
    }

    // 1. Read image bytes
    final bytes = await File(imagePath).readAsBytes();
    final image = img.decodeImage(bytes);
    if (image == null) {
      throw Exception("Failed to decode image.");
    }

    // 2. Resize to 224x224
    final resized = img.copyResize(image, width: 224, height: 224);

    // 3. Preprocess to raw unnormalized Float32List [1, 224, 224, 3] (range [0, 255])
    final inputBuffer = Float32List(1 * 224 * 224 * 3);
    var index = 0;
    for (var y = 0; y < 224; y++) {
      for (var x = 0; x < 224; x++) {
        final pixel = resized.getPixel(x, y);
        inputBuffer[index++] = pixel.r.toDouble();
        inputBuffer[index++] = pixel.g.toDouble();
        inputBuffer[index++] = pixel.b.toDouble();
      }
    }

    // 4. Run model inference
    final outputBuffer = Float32List(14).reshape([1, 14]);
    _interpreter!.run(inputBuffer.reshape([1, 224, 224, 3]), outputBuffer);

    // 5. Process prediction outputs
    final List<double> confidenceList = List<double>.from(outputBuffer[0]);

    // Find highest confidence index
    var bestIndex = 0;
    var maxConfidence = -1.0;
    for (var i = 0; i < confidenceList.length; i++) {
      if (confidenceList[i] > maxConfidence) {
        maxConfidence = confidenceList[i];
        bestIndex = i;
      }
    }

    // --- OOD Detection ---
    // Layer 1: Confidence threshold — model must be at least 60% confident
    const double confidenceThreshold = 0.85;

    // Layer 2: Entropy check — high entropy means the model is uncertain/spread
    // Shannon entropy: H = -sum(p * log(p)). Max entropy for 14 classes = log(14) ≈ 2.64
    final double entropy = confidenceList.fold(0.0, (sum, p) {
      if (p <= 0) return sum;
      return sum - p * log(p);
    });
    const double maxPossibleEntropy = 2.6390573; // log(14)
    final double normalizedEntropy =
        entropy / maxPossibleEntropy; // 0.0 = certain, 1.0 = totally uncertain
    const double entropyThreshold =
        0.65; // flag as unknown if entropy > 65% of max

    bool isUnknown = false;
    String? uncertaintyReason;

    if (maxConfidence < confidenceThreshold) {
      isUnknown = true;
      uncertaintyReason =
          'Low confidence (${(maxConfidence * 100).toStringAsFixed(1)}%). '
          'This crop may not be supported.';
    } else if (normalizedEntropy > entropyThreshold) {
      isUnknown = true;
      uncertaintyReason =
          'High prediction uncertainty (entropy: ${(normalizedEntropy * 100).toStringAsFixed(1)}%). '
          'This crop may not be supported.';
    }

    final String predictedClass = isUnknown
        ? 'Unknown / Unsupported Crop'
        : _labels![bestIndex];

    return {
      'classIndex': isUnknown ? -1 : bestIndex,
      'predictedClass': predictedClass,
      'confidence': maxConfidence,
      'allConfidence': confidenceList,
      'labels': _labels,
      'isUnknown': isUnknown,
      'uncertaintyReason': uncertaintyReason,
      'normalizedEntropy': normalizedEntropy,
    };
  }

  static void dispose() {
    _interpreter?.close();
    _interpreter = null;
  }
}
