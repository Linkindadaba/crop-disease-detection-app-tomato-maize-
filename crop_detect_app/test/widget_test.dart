import 'package:flutter_test/flutter_test.dart';
import 'package:crop_detect_app/main.dart';

void main() {
  testWidgets('App compiles and mounts successfully', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const MyApp(hasSession: false));
    
    // Verify that MyApp is in the widget tree.
    expect(find.byType(MyApp), findsOneWidget);
  });
}
