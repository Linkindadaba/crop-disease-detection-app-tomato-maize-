import 'dart:io';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';
import '../services/db_service.dart';
import '../services/tflite_service.dart';
import '../services/user_session_service.dart';
import 'scan_details_screen.dart';
import 'history_screen.dart';
import 'onboarding_screen.dart';
import 'reviews_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ImagePicker _picker = ImagePicker();
  List<Map<String, dynamic>> _recentHistory = [];
  bool _isLoading = false;
  String _userName = 'Farmer';
  String _userLocation = '';

  @override
  void initState() {
    super.initState();
    _loadHistory();
    _loadUserSession();
  }

  Future<void> _loadUserSession() async {
    final name = await UserSessionService.getName();
    final location = await UserSessionService.getLocation();
    if (mounted) {
      setState(() {
        _userName = name;
        _userLocation = location;
      });
    }
  }

  Future<void> _loadHistory() async {
    final history = await DbService.getHistory();
    setState(() {
      _recentHistory = history.take(5).toList(); // Show top 5 recent in dashboard
    });
  }

  Future<void> _processDiagnosis(ImageSource source) async {
    try {
      final XFile? pickedFile = await _picker.pickImage(
        source: source,
        maxWidth: 500,
        maxHeight: 500,
      );

      if (pickedFile == null) return;

      setState(() {
        _isLoading = true;
      });

      // Initialize TFLite service if not already done
      if (!TfliteService.isInitialized) {
        await TfliteService.init();
      }

      // Run inference
      final result = await TfliteService.runInference(pickedFile.path);
      
      final String rawClass = result['predictedClass'];
      final double confidence = result['confidence'];
      final bool isUnknown = result['isUnknown'] ?? false;
      final String? uncertaintyReason = result['uncertaintyReason'];

      // Deduce crop type (maize or tomato) — only for known crops
      final String cropType = rawClass.toLowerCase().contains("tomato") ? "Tomato" : "Maize";

      // Log into history database only for known crops
      if (!isUnknown) {
        await DbService.addDiagnosis(cropType, rawClass, confidence, pickedFile.path);
      }

      setState(() {
        _isLoading = false;
      });

      // Reload history list in dashboard
      _loadHistory();

      // Navigate to details screen
      if (mounted) {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => ScanDetailsScreen(
              imagePath: pickedFile.path,
              cropType: cropType,
              className: rawClass,
              confidence: confidence,
              isUnknown: isUnknown,
              uncertaintyReason: uncertaintyReason,
            ),
          ),
        );
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text("Diagnosis Error: $e"),
            backgroundColor: Colors.redAccent,
          ),
        );
      }
    }
  }

  String _cleanClassName(String raw) {
    // Replaces underscores and structures with friendly names
    String clean = raw
        .replaceAll("Corn_(maize)___", "Maize - ")
        .replaceAll("Tomato___", "Tomato - ")
        .replaceAll("___", " ")
        .replaceAll("_", " ");
    
    // Capitalize first letters
    return clean.split(' ').map((word) {
      if (word.isEmpty) return '';
      return word[0].toUpperCase() + word.substring(1);
    }).join(' ');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF9FBF9),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: Text(
          'AgriGuard AI',
          style: GoogleFonts.outfit(
            color: const Color(0xFF1E3A1E),
            fontWeight: FontWeight.bold,
            fontSize: 24,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_outline_rounded, color: Color(0xFF2E7D32)),
            tooltip: 'Edit Profile',
            onPressed: () async {
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const OnboardingScreen()),
              );
              _loadUserSession();
            },
          ),
          IconButton(
            icon: const Icon(Icons.star_outline_rounded, color: Color(0xFF2E7D32)),
            tooltip: 'Rate & Reviews',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const ReviewsScreen()),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.history_rounded, color: Color(0xFF2E7D32)),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const HistoryScreen()),
              ).then((_) => _loadHistory());
            },
          )
        ],
      ),
      body: _isLoading
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(
                    color: Color(0xFF2E7D32),
                  ),
                  SizedBox(height: 16),
                  Text(
                    "Analyzing crop pathology...",
                    style: TextStyle(
                      color: Color(0xFF1E3A1E),
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            )
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Ghanaian greeting banner
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF2E7D32), Color(0xFF1B5E20)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                          color: const Color(0xFF2E7D32).withValues(alpha: 77),
                          blurRadius: 12,
                          offset: const Offset(0, 6),
                        )
                      ],
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        // Text content
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Welcome, $_userName!',
                                style: GoogleFonts.outfit(
                                  color: Colors.white,
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 4),
                              if (_userLocation.isNotEmpty)
                                Text(
                                  '📍 $_userLocation',
                                  style: const TextStyle(
                                    color: Color(0xFFB9F6CA),
                                    fontSize: 12,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              const SizedBox(height: 6),
                              const Text(
                                'Scan maize or tomato leaves to diagnose crop diseases entirely offline.',
                                style: TextStyle(
                                  color: Color(0xFFE8F5E9),
                                  fontSize: 13,
                                  height: 1.4,
                                ),
                              ),
                              const SizedBox(height: 12),
                              FittedBox(
                                fit: BoxFit.scaleDown,
                                alignment: Alignment.centerLeft,
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                  decoration: BoxDecoration(
                                    color: Colors.white.withValues(alpha: 51),
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: const Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(Icons.offline_bolt_rounded, color: Colors.amber, size: 16),
                                      SizedBox(width: 6),
                                      Text(
                                        '100% Offline Mode Active',
                                        style: TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.bold,
                                          fontSize: 11,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        // Farmer hero image
                        ClipRRect(
                          borderRadius: BorderRadius.circular(14),
                          child: Image.asset(
                            'assets/images/farmer_hero.png',
                            width: 100,
                            height: 120,
                            fit: BoxFit.cover,
                            errorBuilder: (context, error, stackTrace) =>
                                const SizedBox.shrink(),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Diagnostics controls title
                  Text(
                    'Leaf Diagnostics Scanner',
                    style: GoogleFonts.outfit(
                      color: const Color(0xFF1E3A1E),
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),

                  Row(
                    children: [
                      // Camera Option — disabled on Windows (no camera delegate support)
                      Expanded(
                        child: Tooltip(
                          message: Platform.isWindows
                              ? 'Camera not available on Windows. Use Gallery Upload instead.'
                              : '',
                          child: GestureDetector(
                            onTap: Platform.isWindows
                                ? null
                                : () => _processDiagnosis(ImageSource.camera),
                            child: Opacity(
                              opacity: Platform.isWindows ? 0.45 : 1.0,
                              child: Container(
                                height: 120,
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(16),
                                  border: Border.all(
                                    color: Platform.isWindows
                                        ? const Color(0xFFBDBDBD)
                                        : const Color(0xFFE0E0E0),
                                  ),
                                ),
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    CircleAvatar(
                                      radius: 26,
                                      backgroundColor: Platform.isWindows
                                          ? const Color(0xFFF5F5F5)
                                          : const Color(0xFFE8F5E9),
                                      child: Icon(
                                        Icons.photo_camera_rounded,
                                        color: Platform.isWindows
                                            ? Colors.grey
                                            : const Color(0xFF2E7D32),
                                        size: 28,
                                      ),
                                    ),
                                    const SizedBox(height: 10),
                                    Text(
                                      'Camera Scan',
                                      style: GoogleFonts.outfit(
                                        fontWeight: FontWeight.w600,
                                        color: Platform.isWindows
                                            ? Colors.grey
                                            : const Color(0xFF1E3A1E),
                                        fontSize: 14,
                                      ),
                                    ),
                                    if (Platform.isWindows)
                                      const Text(
                                        'Not available',
                                        style: TextStyle(
                                          fontSize: 10,
                                          color: Colors.grey,
                                        ),
                                      ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 16),
                      // Gallery Option
                      Expanded(
                        child: GestureDetector(
                          onTap: () => _processDiagnosis(ImageSource.gallery),
                          child: Container(
                            height: 120,
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: const Color(0xFFE0E0E0)),
                            ),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const CircleAvatar(
                                  radius: 26,
                                  backgroundColor: Color(0xFFFFF3E0),
                                  child: Icon(Icons.photo_library_rounded, color: Colors.orange, size: 28),
                                ),
                                const SizedBox(height: 10),
                                Text(
                                  'Gallery Upload',
                                  style: GoogleFonts.outfit(
                                    fontWeight: FontWeight.w600,
                                    color: const Color(0xFF1E3A1E),
                                    fontSize: 14,
                                  ),
                                )
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 30),

                  // Recent activity section
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Recent History Logs',
                        style: GoogleFonts.outfit(
                          color: const Color(0xFF1E3A1E),
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (_recentHistory.isNotEmpty)
                        TextButton(
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(builder: (context) => const HistoryScreen()),
                            ).then((_) => _loadHistory());
                          },
                          child: const Text(
                            'See All',
                            style: TextStyle(
                              color: Color(0xFF2E7D32),
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        )
                    ],
                  ),
                  const SizedBox(height: 10),

                  if (_recentHistory.isEmpty)
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 40),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: const Color(0xFFEEEEEE)),
                      ),
                      child: const Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.search_off_rounded, color: Colors.grey, size: 40),
                          SizedBox(height: 12),
                          Text(
                            'No crop diagnosis logged yet.',
                            style: TextStyle(color: Colors.grey, fontSize: 14),
                          )
                        ],
                      ),
                    )
                  else
                    ListView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: _recentHistory.length,
                      itemBuilder: (context, index) {
                        final item = _recentHistory[index];
                        final String pClass = item['predicted_class'];
                        final double conf = item['confidence'];
                        final String imgPath = item['image_path'];
                        final String dateStr = item['timestamp'].toString().substring(0, 10);
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
                            trailing: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: isHealthy
                                    ? const Color(0xFFE8F5E9)
                                    : const Color(0xFFFFEBEE),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                isHealthy ? 'Healthy' : 'Diseased',
                                style: TextStyle(
                                  color: isHealthy ? const Color(0xFF2E7D32) : Colors.red,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 10,
                                ),
                              ),
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
                              );
                            },
                          ),
                        );
                      },
                    ),
                  const SizedBox(height: 20),

                  // Ghana System Usability Scale Benchmark Card
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE8F5E9),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: const Color(0xFFC8E6C9)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.star_rounded, color: Colors.amber),
                            const SizedBox(width: 6),
                            Text(
                              'Field Usability Benchmark',
                              style: GoogleFonts.outfit(
                                color: const Color(0xFF1B5E20),
                                fontWeight: FontWeight.bold,
                                fontSize: 15,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'The local system was evaluated with Ghanaian farmers and extension officers, achieving a mean SUS score of 76.5 (representing Grade B usability rating).',
                          style: TextStyle(
                            color: Color(0xFF2E7D32),
                            fontSize: 12,
                            height: 1.4,
                          ),
                        )
                      ],
                    ),
                  )
                ],
              ),
            ),
    );
  }
}
