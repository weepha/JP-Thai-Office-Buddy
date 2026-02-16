import 'package:flutter/material.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  final List<Map<String, dynamic>> features = const [
    {
      'title': 'แปลภาษา\n(Translator)',
      'icon': Icons.translate,
      'route': '/translator',
      'color': Colors.blueAccent,
    },
    {
      'title': 'ผู้ช่วยร่างเอกสาร\n(Doc Assistant)',
      'icon': Icons.description,
      'route': '/doc_assistant',
      'color': Colors.orangeAccent,
    },
    {
      'title': 'คลังศัพท์\n(Glossary)',
      'icon': Icons.library_books,
      'route': '/glossary',
      'color': Colors.green,
    },
    {
      'title': 'แปลจากภาพ\n(OCR/Vision)',
      'icon': Icons.camera_alt,
      'route': '/vision',
      'color': Colors.purpleAccent,
    },
    {
      'title': 'ตรวจสอบความสุภาพ\n(Politeness)',
      'icon': Icons.verified_user,
      'route': '/politeness',
      'color': Colors.teal,
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('JP-Thai Office Buddy 🇹🇭🇯🇵'),
        centerTitle: true,
        elevation: 0,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            const Text(
              'เลือกฟีเจอร์ที่ต้องการใช้งาน',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: GridView.builder(
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 16,
                  childAspectRatio: 1.1,
                ),
                itemCount: features.length,
                itemBuilder: (context, index) {
                  final feature = features[index];
                  return Card(
                    elevation: 4,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    color: feature['color'].withOpacity(0.1),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(16),
                      onTap: () {
                         if (feature['route'] == '/doc_assistant') {
                           Navigator.pushNamed(context, feature['route']);
                         } else if (feature['route'] == '/translator') {
                           Navigator.pushNamed(context, feature['route']);
                         } else if (feature['route'] == '/glossary') {
                           Navigator.pushNamed(context, feature['route']);
                         } else {
                           ScaffoldMessenger.of(context).showSnackBar(
                             SnackBar(content: Text('กำลังไปที่: ${feature['title']}')),
                           );
                         }
                      },
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            feature['icon'],
                            size: 48,
                            color: feature['color'],
                          ),
                          const SizedBox(height: 12),
                          Text(
                            feature['title'],
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
