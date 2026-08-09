import 'dart:io';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/db_service.dart';
import 'scan_details_screen.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _history = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final history = await DbService.getHistory();
    setState(() {
      _history = history;
      _loading = false;
    });
  }

  Future<void> _deleteItem(int id) async {
    await DbService.deleteHistoryItem(id);
    _loadHistory();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Log deleted successfully"),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  String _cleanClassName(String raw) {
    String clean = raw
        .replaceAll("Corn_(maize)___", "Maize - ")
        .replaceAll("Tomato___", "Tomato - ")
        .replaceAll("___", " ")
        .replaceAll("_", " ");

    return clean
        .split(' ')
        .map((word) {
          if (word.isEmpty) return '';
          return word[0].toUpperCase() + word.substring(1);
        })
        .join(' ');
  }

  @override
  Widget build(BuildContext context) {
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
          'Diagnostic History',
          style: GoogleFonts.outfit(
            color: const Color(0xFF1E3A1E),
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _history.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.history_rounded,
                    size: 60,
                    color: Colors.grey,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'No history logged yet.',
                    style: GoogleFonts.outfit(
                      color: Colors.grey,
                      fontSize: 16,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: _history.length,
              itemBuilder: (context, index) {
                final item = _history[index];
                final int id = item['id'];
                final String pClass = item['predicted_class'];
                final double conf = item['confidence'];
                final String imgPath = item['image_path'];
                final String timestamp = item['timestamp'].toString();

                // Simple date parsing
                final String dateStr = timestamp.contains('T')
                    ? timestamp.split('T')[0]
                    : timestamp.substring(0, 10);

                final bool isHealthy = pClass.toLowerCase().contains("healthy");

                return Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFFEEEEEE)),
                  ),
                  child: ListTile(
                    leading: Container(
                      width: 50,
                      height: 50,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(8),
                        image: DecorationImage(
                          image: FileImage(File(imgPath)),
                          fit: BoxFit.cover,
                        ),
                      ),
                    ),
                    title: Text(
                      _cleanClassName(pClass),
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF1E3A1E),
                        fontSize: 14,
                      ),
                    ),
                    subtitle: Text(
                      'Date: $dateStr  •  Conf: ${(conf * 100).toStringAsFixed(1)}%',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: isHealthy
                                ? const Color(0xFFE8F5E9)
                                : const Color(0xFFFFEBEE),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            isHealthy ? 'Healthy' : 'Diseased',
                            style: TextStyle(
                              color: isHealthy
                                  ? const Color(0xFF2E7D32)
                                  : Colors.red,
                              fontWeight: FontWeight.bold,
                              fontSize: 10,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton(
                          icon: const Icon(
                            Icons.delete_outline_rounded,
                            color: Colors.redAccent,
                            size: 20,
                          ),
                          onPressed: () => _deleteItem(id),
                        ),
                      ],
                    ),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (context) => ScanDetailsScreen(
                            imagePath: imgPath,
                            cropType: item['crop_type'],
                            className: pClass,
                            confidence: conf,
                          ),
                        ),
                      ).then((_) => _loadHistory());
                    },
                  ),
                );
              },
            ),
    );
  }
}
