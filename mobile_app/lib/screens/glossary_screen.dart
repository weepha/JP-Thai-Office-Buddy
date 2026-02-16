import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class GlossaryScreen extends StatefulWidget {
  const GlossaryScreen({super.key});

  @override
  State<GlossaryScreen> createState() => _GlossaryScreenState();
}

class _GlossaryScreenState extends State<GlossaryScreen> {
  final _controller = TextEditingController();
  bool _isLoading = false;
  Map<String, dynamic>? _result;
  String? _error;

  Future<void> _search() async {
    if (_controller.text.isEmpty) return;

    setState(() {
      _isLoading = true;
      _result = null;
      _error = null;
    });

    try {
      // For Chrome/Web use localhost (127.0.0.1)
      final url = Uri.parse('http://127.0.0.1:5000/search_glossary');
      
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'term': _controller.text}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['error'] != null) {
          setState(() {
            _error = data['error'];
          });
        } else {
          setState(() {
            _result = data;
          });
        }
      } else {
        setState(() {
          _error = 'Server Error: ${response.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Connection Error: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('คลังศัพท์เทคนิค (Glossary)')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _controller,
              decoration: const InputDecoration(
                labelText: 'ค้นหาคำศัพท์',
                hintText: 'เช่น Kaizen, Horenso, Ringi',
                border: OutlineInputBorder(),
                suffixIcon: Icon(Icons.search),
              ),
              onSubmitted: (_) => _search(),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _isLoading ? null : _search,
              icon: _isLoading 
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : const Icon(Icons.search),
              label: const Text('ค้นหา (Search)'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.teal,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
            const SizedBox(height: 24),
            if (_error != null)
              Container(
                padding: const EdgeInsets.all(12),
                color: Colors.red[50],
                child: Text('Error: $_error', style: const TextStyle(color: Colors.red)),
              ),
            if (_result != null)
              Card(
                elevation: 4,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _result!['term_jp'] ?? '-',
                        style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.teal),
                      ),
                      const Divider(),
                      const Text('ความหมาย:', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                      Text(_result!['definition'] ?? '-', style: const TextStyle(fontSize: 16)),
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.grey[100],
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: Colors.grey[300]!),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('ตัวอย่างประโยค:', style: TextStyle(fontWeight: FontWeight.bold)),
                            const SizedBox(height: 4),
                            Text(_result!['example_jp'] ?? '-', style: const TextStyle(fontSize: 16, fontStyle: FontStyle.italic)),
                            const SizedBox(height: 4),
                            Text(_result!['example_th'] ?? '-', style: const TextStyle(color: Colors.grey)),
                          ],
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
}
