import 'dart:io';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/db_service.dart';

class ScanDetailsScreen extends StatefulWidget {
  final String imagePath;
  final String cropType;
  final String className;
  final double confidence;
  final bool isUnknown;
  final String? uncertaintyReason;

  const ScanDetailsScreen({
    super.key,
    required this.imagePath,
    required this.cropType,
    required this.className,
    required this.confidence,
    this.isUnknown = false,
    this.uncertaintyReason,
  });

  @override
  State<ScanDetailsScreen> createState() => _ScanDetailsScreenState();
}

class _ScanDetailsScreenState extends State<ScanDetailsScreen> {
  Map<String, dynamic>? _treatment;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadTreatments();
  }

  Future<void> _loadTreatments() async {
    final treatment = await DbService.getTreatmentByClass(widget.className);
    setState(() {
      _treatment = treatment;
      _loading = false;
    });
  }

  String _cleanClassName(String raw) {
    String clean = raw
        .replaceAll("Corn_(maize)___", "Maize - ")
        .replaceAll("Tomato___", "Tomato - ")
        .replaceAll("___", " ")
        .replaceAll("_", " ");
    
    return clean.split(' ').map((word) {
      if (word.isEmpty) return '';
      return word[0].toUpperCase() + word.substring(1);
    }).join(' ');
  }

  @override
  Widget build(BuildContext context) {
    final cleanName = _cleanClassName(widget.className);
    final isHealthy = widget.className.toLowerCase().contains("healthy");
    final isUnknown = widget.isUnknown;
    final statusColor = isUnknown
        ? const Color(0xFFF57F17) // amber for unknown
        : isHealthy
            ? const Color(0xFF2E7D32)
            : const Color(0xFFC62828);

    return Scaffold(
      backgroundColor: const Color(0xFFF9FBF9),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: Color(0xFF1E3A1E)),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Diagnostic Report',
          style: GoogleFonts.outfit(
            color: const Color(0xFF1E3A1E),
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Captured Leaf Image
            Container(
              height: 250,
              width: double.infinity,
              decoration: BoxDecoration(
                image: DecorationImage(
                  image: FileImage(File(widget.imagePath)),
                  fit: BoxFit.cover,
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Main Diagnostic Summary Badge
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 20),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: statusColor.withValues(alpha: 77), width: 1.5),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isUnknown
                              ? 'UNSUPPORTED CROP'
                              : isHealthy
                                  ? 'HEALTHY CROP DETECTED'
                                  : 'DISEASE DETECTED',
                          style: GoogleFonts.outfit(
                            color: statusColor,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                            letterSpacing: 1.1,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          isUnknown ? 'Unknown / Unsupported Crop' : cleanName,
                          style: GoogleFonts.outfit(
                            color: const Color(0xFF1E3A1E),
                            fontWeight: FontWeight.bold,
                            fontSize: 20,
                          ),
                        ),
                        if (isUnknown) ...[
                          const SizedBox(height: 10),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Icon(Icons.warning_amber_rounded,
                                  color: Color(0xFFF57F17), size: 18),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  widget.uncertaintyReason ??
                                      'The scanned leaf does not match any supported crop. '
                                      'Please use a supported crop leaf.',
                                  style: const TextStyle(
                                    color: Color(0xFF795548),
                                    fontSize: 13,
                                    height: 1.4,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ] else ...[
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              Expanded(
                                child: LinearProgressIndicator(
                                  value: widget.confidence,
                                  backgroundColor: Colors.grey[200],
                                  color: statusColor,
                                  minHeight: 8,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Text(
                                '${(widget.confidence * 100).toStringAsFixed(1)}%',
                                style: TextStyle(
                                  color: statusColor,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Recommendations Section
                  if (isUnknown)
                    _buildCard(
                      title: 'What to do?',
                      content:
                          'This app currently supports the following crops:\n\n'
                          '• Tomato\n• Corn (Maize)\n\n'
                          'Please retake the photo using a leaf from one of the supported crops. '
                          'Make sure the leaf is well-lit, in focus, and fills most of the frame.',
                      icon: Icons.help_outline_rounded,
                      iconColor: const Color(0xFFF57F17),
                    )
                  else ...[
                    Text(
                      'Pathological Recommendations',
                      style: GoogleFonts.outfit(
                        color: const Color(0xFF1E3A1E),
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),

                    _loading
                        ? const Center(child: CircularProgressIndicator())
                        : _treatment == null
                            ? const Text("No recommendation found in offline database.")
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Description Card
                                  _buildCard(
                                    title: 'Pathology Description',
                                    content: _treatment!['description'] ?? 'N/A',
                                    icon: Icons.info_outline_rounded,
                                    iconColor: Colors.blue,
                                  ),
                                  const SizedBox(height: 16),

                                  // Prevention Card
                                  _buildCard(
                                    title: '🌱 Prevention Measures',
                                    content: _treatment!['prevention'] ?? 'N/A',
                                    icon: Icons.eco_outlined,
                                    iconColor: Colors.green,
                                  ),
                                  const SizedBox(height: 16),

                                  // If crop is healthy, do not display chemical/organic treatment headers
                                  if (!isHealthy) ...[
                                    // Organic Card
                                    _buildCard(
                                      title: '🍂 Organic Treatments',
                                      content: _treatment!['organic'] ?? 'N/A',
                                      icon: Icons.grass_rounded,
                                      iconColor: Colors.teal,
                                    ),
                                    const SizedBox(height: 16),

                                    // Chemical Card
                                    _buildCard(
                                      title: '🧪 Chemical Treatments',
                                      content: _treatment!['chemical'] ?? 'N/A',
                                      icon: Icons.science_outlined,
                                      iconColor: Colors.redAccent,
                                    ),
                                    const SizedBox(height: 16),
                                  ],
                                ],
                              ),
                  ],
                ],
              ),
            )
          ],
        ),
      ),
    );
  }

  Widget _buildCard({
    required String title,
    required String content,
    required IconData icon,
    required Color iconColor,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFEEEEEE)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: iconColor, size: 20),
              const SizedBox(width: 8),
              Text(
                title,
                style: GoogleFonts.outfit(
                  color: const Color(0xFF1E3A1E),
                  fontWeight: FontWeight.bold,
                  fontSize: 15,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            content,
            style: const TextStyle(
              color: Color(0xFF555555),
              fontSize: 13.5,
              height: 1.5,
            ),
            textAlign: TextAlign.justify,
          ),
        ],
      ),
    );
  }
}
