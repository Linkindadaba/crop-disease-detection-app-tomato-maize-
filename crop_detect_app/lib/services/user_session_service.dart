import 'package:shared_preferences/shared_preferences.dart';

class UserSessionService {
  static const String _keyName = 'user_name';
  static const String _keyLocation = 'user_location';
  static const String _keyHasSession = 'has_session';

  // Check if a user session already exists
  static Future<bool> hasSession() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyHasSession) ?? false;
  }

  // Save a new user session
  static Future<void> saveSession({
    required String name,
    String location = '',
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyName, name.trim());
    await prefs.setString(_keyLocation, location.trim());
    await prefs.setBool(_keyHasSession, true);
  }

  // Get the stored user name
  static Future<String> getName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_keyName) ?? 'Farmer';
  }

  // Get the stored user location
  static Future<String> getLocation() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_keyLocation) ?? '';
  }

  // Update name (for profile editing)
  static Future<void> updateName(String name) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyName, name.trim());
  }

  // Update location
  static Future<void> updateLocation(String location) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyLocation, location.trim());
  }

  // Clear session (logout / reset)
  static Future<void> clearSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  }
}
