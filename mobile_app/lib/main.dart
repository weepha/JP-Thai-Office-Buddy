import 'package:flutter/material.dart';
import 'screens/dashboard_screen.dart';
import 'screens/doc_assistant_screen.dart';
import 'screens/translator_screen.dart';
import 'screens/glossary_screen.dart';
import 'screens/vision_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'JP-Thai Office Buddy',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
        fontFamily: 'Roboto', // Default font, can be changed to Thai font later
      ),
      home: const DashboardScreen(),
      routes: {
        '/translator': (context) => const TranslatorScreen(),
        '/doc_assistant': (context) => const DocAssistantScreen(),
        '/glossary': (context) => const GlossaryScreen(),
        '/vision': (context) => const VisionScreen(),
        // '/politeness': (context) => const PolitenessScreen(),
      },
    );
  }
}
