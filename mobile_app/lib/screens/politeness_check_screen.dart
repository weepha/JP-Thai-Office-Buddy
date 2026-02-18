import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../services/api_config.dart';

class PolitenessCheckScreen extends StatefulWidget {
  const PolitenessCheckScreen({super.key});

  @override
  State<PolitenessCheckScreen> createState() => _PolitenessCheckScreenState();
}

class _PolitenessCheckScreenState extends State<PolitenessCheckScreen> {
  final TextEditingController _textController = TextEditingController();
  String _selectedRecipient = 'Head/Boss';
  final List<String> _recipients = [
    'Head/Boss',
    'Client',
    'Colleague',
    'Junior',
  ];

  bool _isLoading = false;
  Map<String, dynamic>? _result;
  String? _error;

  Future<void> _analyzePoliteness() async {
    setState(() {
      _isLoading = true;
      _result = null;
      _error = null;
    });

    try {
      // Use centralized API Config
      final url = Uri.parse('${ApiConfig.baseUrl}/analyze_politeness');

      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'text': _textController.text,
          'recipient': _selectedRecipient,
        }),
      );

      if (response.statusCode == 200) {
        setState(() {
          _result = json.decode(response.body);
        });
      } else {
        setState(() {
          _error = 'Error: ${response.statusCode}';
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
      appBar: AppBar(
        title: const Text('Politeness Check'),
        backgroundColor: Colors.indigo,
        foregroundColor: Colors.white,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Enter Japanese text to check:',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _textController,
                maxLines: 3,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'e.g., Mizu kudasai',
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Recipient Status:',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              DropdownButton<String>(
                value: _selectedRecipient,
                isExpanded: true,
                items: _recipients.map((String value) {
                  return DropdownMenuItem<String>(
                    value: value,
                    child: Text(value),
                  );
                }).toList(),
                onChanged: (newValue) {
                  setState(() {
                    _selectedRecipient = newValue!;
                  });
                },
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _isLoading ? null : _analyzePoliteness,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.indigo,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text('Analyze Politeness'),
              ),
              const SizedBox(height: 24),
              if (_error != null)
                Text(_error!, style: const TextStyle(color: Colors.red)),
              if (_result != null) ...[
                _buildResultCard(
                  'Analysis',
                  _result!['analysis'],
                  Colors.orange.shade100,
                ),
                const SizedBox(height: 12),
                _buildResultCard(
                  'Suggestion',
                  _result!['suggestion'],
                  Colors.green.shade100,
                ),
                const SizedBox(height: 12),
                _buildResultCard(
                  'Explanation',
                  _result!['explanation'],
                  Colors.blue.shade100,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResultCard(String title, String content, Color color) {
    return Card(
      color: color,
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 4),
            Text(content, style: const TextStyle(fontSize: 14)),
          ],
        ),
      ),
    );
  }
}
