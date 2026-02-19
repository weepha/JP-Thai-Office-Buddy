import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../services/speech_service.dart';
import '../services/api_config.dart';

class TranslatorScreen extends StatefulWidget {
  const TranslatorScreen({super.key});

  @override
  State<TranslatorScreen> createState() => _TranslatorScreenState();
}

class _TranslatorScreenState extends State<TranslatorScreen> {
  final _controller = TextEditingController();
  bool _isLoading = false;
  Map<String, String>? _results;

  String? _error;
  final SpeechService _speechService = SpeechService();
  bool _isListening = false;

  void _toggleListening() async {
    if (_isListening) {
      await _speechService.stopListening();
      setState(() => _isListening = false);
    } else {
      bool available = await _speechService.initSpeech();
      if (available) {
        setState(() => _isListening = true);
        _speechService.startListening(
          onResult: (text) {
            setState(() {
              _controller.text = text;
            });
          },
          localeId: 'th_TH', // Thai input
        );

        // Auto stop after some time or silence (handled by service, but good to reset state)
        Future.delayed(const Duration(seconds: 5), () {
          if (mounted && !_speechService.isListening) {
            setState(() => _isListening = false);
          }
        });
      } else {
        setState(
          () =>
              _error = "Speech recognition not available or permission denied",
        );
      }
    }
  }

  Future<void> _translate() async {
    if (_controller.text.isEmpty) return;

    setState(() {
      _isLoading = true;
      _results = null;
      _error = null;
    });

    try {
      // Use centralized API Config
      final url = Uri.parse('${ApiConfig.baseUrl}/translate');

      final response = await http.post(
        url,
        body: {'text_input': _controller.text},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          if (data['error'] != null) {
            _error = data['error'];
          } else {
            _results = {
              'casual': data['casual'] ?? '-',
              'polite': data['polite'] ?? '-',
              'business': data['business'] ?? '-',
            };
          }
        });
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
      appBar: AppBar(title: const Text('แปลภาษา (Translator)')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              autofocus: true,
              controller: _controller,
              decoration: InputDecoration(
                labelText: 'พิมพ์ประโยคภาษาไทย',
                hintText: 'เช่น ขอบคุณครับ, ขอโทษที่มาสาย',
                border: OutlineInputBorder(),

                suffixIcon: IconButton(
                  icon: Icon(_isListening ? Icons.mic : Icons.mic_none),
                  color: _isListening ? Colors.red : Colors.grey,
                  onPressed: _toggleListening,
                ),
              ),
              maxLines: 3,
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _isLoading ? null : _translate,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blueAccent,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
              child: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                  : const Text(
                      'แปลภาษา (Translate)',
                      style: TextStyle(fontSize: 18),
                    ),
            ),
            const SizedBox(height: 24),
            if (_error != null)
              Container(
                padding: const EdgeInsets.all(12),
                color: Colors.red[50],
                child: Text(
                  'Error: $_error',
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            if (_results != null) ...[
              _buildResultCard(
                'Business (ทางการ/ลูกค้า)',
                _results!['business']!,
                Colors.blueGrey,
              ),
              _buildResultCard(
                'Polite (สุภาพทั่วไป)',
                _results!['polite']!,
                Colors.green,
              ),
              _buildResultCard(
                'Casual (เพื่อน/คนสนิท)',
                _results!['casual']!,
                Colors.orange,
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard(String title, String text, Color color) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: color.withOpacity(0.5)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(fontWeight: FontWeight.bold, color: color),
            ),
            const SizedBox(height: 4),
            SelectableText(text, style: const TextStyle(fontSize: 18)),
          ],
        ),
      ),
    );
  }
}
