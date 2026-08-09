import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../services/db_service.dart';
import '../services/user_session_service.dart';

class ReviewsScreen extends StatefulWidget {
  const ReviewsScreen({super.key});

  @override
  State<ReviewsScreen> createState() => _ReviewsScreenState();
}

class _ReviewsScreenState extends State<ReviewsScreen> {
  final _reviewController = TextEditingController();
  int _selectedRating = 0;
  int _hoverRating = 0;
  bool _isSubmitting = false;
  List<Map<String, dynamic>> _reviews = [];
  String _userName = 'Farmer';
  bool _hasReviewed = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _reviewController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    final name = await UserSessionService.getName();
    final reviews = await DbService.getReviews();
    if (mounted) {
      setState(() {
        _userName = name;
        _reviews = reviews;
        // Check if this user already submitted a review
        _hasReviewed = reviews.any((r) => r['user_name'] == name);
      });
    }
  }

  Future<void> _submitReview() async {
    if (_selectedRating == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select a star rating before submitting.'),
          behavior: SnackBarBehavior.floating,
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() => _isSubmitting = true);

    await DbService.addReview(
      userName: _userName,
      rating: _selectedRating,
      review: _reviewController.text.trim(),
    );

    _reviewController.clear();
    setState(() {
      _selectedRating = 0;
      _isSubmitting = false;
    });

    await _loadData();

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Thank you, $_userName! Your review was submitted. 🌱'),
          behavior: SnackBarBehavior.floating,
          backgroundColor: const Color(0xFF2E7D32),
        ),
      );
    }
  }

  double _averageRating() {
    if (_reviews.isEmpty) return 0;
    final total = _reviews.fold<int>(0, (sum, r) => sum + (r['rating'] as int));
    return total / _reviews.length;
  }

  Map<int, int> _ratingBreakdown() {
    final map = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0};
    for (final r in _reviews) {
      final rating = r['rating'] as int;
      map[rating] = (map[rating] ?? 0) + 1;
    }
    return map;
  }

  String _timeAgo(String isoTimestamp) {
    try {
      final dt = DateTime.parse(isoTimestamp);
      final diff = DateTime.now().difference(dt);
      if (diff.inMinutes < 1) return 'Just now';
      if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
      if (diff.inHours < 24) return '${diff.inHours}h ago';
      if (diff.inDays < 7) return '${diff.inDays}d ago';
      return '${dt.day}/${dt.month}/${dt.year}';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final avg = _averageRating();
    final breakdown = _ratingBreakdown();

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
          'Ratings & Reviews',
          style: GoogleFonts.outfit(
            color: const Color(0xFF1E3A1E),
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Rating Summary Card ──────────────────────
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFEEEEEE)),
              ),
              child: Row(
                children: [
                  // Big average number
                  Column(
                    children: [
                      Text(
                        avg == 0 ? '—' : avg.toStringAsFixed(1),
                        style: GoogleFonts.outfit(
                          fontSize: 52,
                          fontWeight: FontWeight.bold,
                          color: const Color(0xFF1E3A1E),
                          height: 1,
                        ),
                      ),
                      const SizedBox(height: 6),
                      _buildStarRow(avg, size: 18, color: Colors.amber),
                      const SizedBox(height: 4),
                      Text(
                        '${_reviews.length} review${_reviews.length == 1 ? '' : 's'}',
                        style: GoogleFonts.outfit(
                          fontSize: 12,
                          color: Colors.grey[500],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(width: 24),
                  // Breakdown bars
                  Expanded(
                    child: Column(
                      children: [5, 4, 3, 2, 1].map((star) {
                        final count = breakdown[star] ?? 0;
                        final ratio = _reviews.isEmpty
                            ? 0.0
                            : count / _reviews.length;
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Row(
                            children: [
                              Text(
                                '$star',
                                style: GoogleFonts.outfit(
                                  fontSize: 12,
                                  color: Colors.grey[600],
                                ),
                              ),
                              const SizedBox(width: 4),
                              const Icon(Icons.star_rounded,
                                  color: Colors.amber, size: 12),
                              const SizedBox(width: 6),
                              Expanded(
                                child: ClipRRect(
                                  borderRadius: BorderRadius.circular(4),
                                  child: LinearProgressIndicator(
                                    value: ratio,
                                    backgroundColor: const Color(0xFFF5F5F5),
                                    color: Colors.amber,
                                    minHeight: 7,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 6),
                              Text(
                                '$count',
                                style: GoogleFonts.outfit(
                                  fontSize: 11,
                                  color: Colors.grey[500],
                                ),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // ── Write a Review ───────────────────────────
            Text(
              _hasReviewed ? 'Update Your Review' : 'Write a Review',
              style: GoogleFonts.outfit(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                color: const Color(0xFF1E3A1E),
              ),
            ),
            const SizedBox(height: 12),

            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: const Color(0xFFEEEEEE)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Star selector
                  Text(
                    'Tap to rate:',
                    style: GoogleFonts.outfit(
                      fontSize: 13,
                      color: Colors.grey[600],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: List.generate(5, (i) {
                      final star = i + 1;
                      return GestureDetector(
                        onTap: () => setState(() => _selectedRating = star),
                        child: MouseRegion(
                          onEnter: (_) =>
                              setState(() => _hoverRating = star),
                          onExit: (_) =>
                              setState(() => _hoverRating = 0),
                          child: Padding(
                            padding: const EdgeInsets.only(right: 4),
                            child: Icon(
                              Icons.star_rounded,
                              size: 36,
                              color: star <=
                                      (_hoverRating > 0
                                          ? _hoverRating
                                          : _selectedRating)
                                  ? Colors.amber
                                  : const Color(0xFFE0E0E0),
                            ),
                          ),
                        ),
                      );
                    }),
                  ),
                  if (_selectedRating > 0) ...[
                    const SizedBox(height: 4),
                    Text(
                      _ratingLabel(_selectedRating),
                      style: GoogleFonts.outfit(
                        fontSize: 13,
                        color: Colors.amber[700],
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                  const SizedBox(height: 14),

                  // Review text field
                  TextField(
                    controller: _reviewController,
                    maxLines: 3,
                    maxLength: 250,
                    style: GoogleFonts.outfit(fontSize: 14),
                    decoration: InputDecoration(
                      hintText:
                          'Share your experience with AgriGuard AI... (optional)',
                      hintStyle: GoogleFonts.outfit(
                          color: Colors.grey[400], fontSize: 13),
                      filled: true,
                      fillColor: const Color(0xFFF9FBF9),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide:
                            const BorderSide(color: Color(0xFFE0E0E0)),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide:
                            const BorderSide(color: Color(0xFFE0E0E0)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: const BorderSide(
                            color: Color(0xFF2E7D32), width: 1.5),
                      ),
                      counterStyle: GoogleFonts.outfit(
                          fontSize: 11, color: Colors.grey[400]),
                    ),
                  ),
                  const SizedBox(height: 12),

                  // Submit button
                  SizedBox(
                    width: double.infinity,
                    height: 46,
                    child: ElevatedButton(
                      onPressed: _isSubmitting ? null : _submitReview,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF2E7D32),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                        elevation: 0,
                      ),
                      child: _isSubmitting
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2,
                              ),
                            )
                          : Text(
                              'Submit Review',
                              style: GoogleFonts.outfit(
                                fontWeight: FontWeight.bold,
                                fontSize: 15,
                              ),
                            ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 28),

            // ── All Reviews List ─────────────────────────
            if (_reviews.isNotEmpty) ...[
              Text(
                'All Reviews',
                style: GoogleFonts.outfit(
                  fontSize: 17,
                  fontWeight: FontWeight.bold,
                  color: const Color(0xFF1E3A1E),
                ),
              ),
              const SizedBox(height: 12),
              ..._reviews.map((r) => _buildReviewCard(r)),
            ] else
              Center(
                child: Padding(
                  padding: const EdgeInsets.only(top: 20),
                  child: Column(
                    children: [
                      const Icon(Icons.rate_review_outlined,
                          size: 48, color: Color(0xFFBDBDBD)),
                      const SizedBox(height: 8),
                      Text(
                        'No reviews yet.\nBe the first to review!',
                        textAlign: TextAlign.center,
                        style: GoogleFonts.outfit(
                          color: Colors.grey[400],
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildReviewCard(Map<String, dynamic> review) {
    final rating = review['rating'] as int;
    final name = review['user_name'] as String? ?? 'Anonymous';
    final text = review['review'] as String? ?? '';
    final timestamp = review['timestamp'] as String? ?? '';
    final isOwn = name == _userName;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isOwn
            ? const Color(0xFFE8F5E9)
            : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isOwn
              ? const Color(0xFFC8E6C9)
              : const Color(0xFFEEEEEE),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // Avatar
              CircleAvatar(
                radius: 18,
                backgroundColor: const Color(0xFF2E7D32),
                child: Text(
                  name.isNotEmpty ? name[0].toUpperCase() : '?',
                  style: GoogleFonts.outfit(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          name,
                          style: GoogleFonts.outfit(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                            color: const Color(0xFF1E3A1E),
                          ),
                        ),
                        if (isOwn) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFF2E7D32),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              'You',
                              style: GoogleFonts.outfit(
                                fontSize: 10,
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    _buildStarRow(rating.toDouble(), size: 14, color: Colors.amber),
                  ],
                ),
              ),
              Text(
                _timeAgo(timestamp),
                style: GoogleFonts.outfit(
                  fontSize: 11,
                  color: Colors.grey[400],
                ),
              ),
            ],
          ),
          if (text.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              text,
              style: GoogleFonts.outfit(
                fontSize: 13.5,
                color: const Color(0xFF444444),
                height: 1.5,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStarRow(double rating, {double size = 16, Color? color}) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(5, (i) {
        final filled = i < rating.floor();
        final half = !filled && (i < rating);
        return Icon(
          filled
              ? Icons.star_rounded
              : half
                  ? Icons.star_half_rounded
                  : Icons.star_outline_rounded,
          color: color ?? Colors.amber,
          size: size,
        );
      }),
    );
  }

  String _ratingLabel(int rating) {
    switch (rating) {
      case 1:
        return '😞 Poor';
      case 2:
        return '😕 Fair';
      case 3:
        return '😊 Good';
      case 4:
        return '😄 Very Good';
      case 5:
        return '🤩 Excellent!';
      default:
        return '';
    }
  }
}
