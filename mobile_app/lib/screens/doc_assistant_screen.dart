import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../services/api_config.dart';

class DocAssistantScreen extends StatefulWidget {
  const DocAssistantScreen({super.key});

  @override
  State<DocAssistantScreen> createState() => _DocAssistantScreenState();
}

class _DocAssistantScreenState extends State<DocAssistantScreen> {
  final _formKey = GlobalKey<FormState>();
  String _topic = '';
  String _docType = 'Email';
  String _tone = 'Business / สุภาพ';
  String _recipient = '';
  String _result = '';
  bool _isLoading = false;

  final List<String> _docTypes = [
    'Email',
    'Daily Report (Nippou)',
    'Meeting Minutes',
    'Apology Letter',
  ];
  final List<String> _tones = [
    'Business / สุภาพ',
    'Polite / ทั่วไป',
    'Casual / เป็นกันเอง',
  ];

  Future<void> _generateDoc() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();

    setState(() {
      _isLoading = true;
      _result = '';
    });

    // Map UI values to API values
    String apiType = _docType;
    String apiTone = 'business';
    if (_tone.contains('Polite')) apiTone = 'polite';
    if (_tone.contains('Casual')) apiTone = 'casual';

    try {
      // Use centralized API Config
      final url = Uri.parse('${ApiConfig.baseUrl}/generate_doc');

      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'topic': _topic,
          'type': apiType,
          'tone': apiTone,
          'recipient': _recipient.isEmpty ? 'หัวหน้า/ลูกค้า' : _recipient,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          if (data['result'] != null) {
            _result = data['result'];
          } else if (data['error'] != null) {
            _result = 'Error: ${data['error']}';
          }
        });
      } else {
        setState(() {
          _result = 'Server Error: ${response.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        _result = 'Connection Error: $e';
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
      appBar: AppBar(title: const Text('ผู้ช่วยร่างเอกสาร (Doc Assistant)')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                decoration: const InputDecoration(
                  labelText: 'หัวข้อ / ใจความสำคัญ (ภาษาไทย)',
                  hintText:
                      'เช่น ขอลาป่วยเนื่องจากเป็นไข้, สรุปยอดขายประจำเดือน',
                  border: OutlineInputBorder(),
                ),
                maxLines: 2,
                validator: (value) =>
                    value == null || value.isEmpty ? 'กรุณาระบุหัวข้อ' : null,
                onSaved: (value) => _topic = value!,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _docType,
                decoration: const InputDecoration(
                  labelText: 'ประเภทเอกสาร',
                  border: OutlineInputBorder(),
                ),
                items: _docTypes
                    .map(
                      (type) =>
                          DropdownMenuItem(value: type, child: Text(type)),
                    )
                    .toList(),
                onChanged: (value) => setState(() => _docType = value!),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                value: _tone,
                decoration: const InputDecoration(
                  labelText: 'ระดับภาษา (Tone)',
                  border: OutlineInputBorder(),
                ),
                items: _tones
                    .map(
                      (tone) =>
                          DropdownMenuItem(value: tone, child: Text(tone)),
                    )
                    .toList(),
                onChanged: (value) => setState(() => _tone = value!),
              ),
              const SizedBox(height: 16),
              TextFormField(
                decoration: const InputDecoration(
                  labelText: 'ผู้รับสาร (Optional)',
                  hintText: 'เช่น Tanaka-san, ลูกค้าบริษัท ABC',
                  border: OutlineInputBorder(),
                ),
                onSaved: (value) => _recipient = value ?? '',
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: _isLoading ? null : _generateDoc,
                icon: _isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.auto_awesome),
                label: Text(
                  _isLoading ? 'กำลังร่างเอกสาร...' : 'สร้างเอกสาร (Generate)',
                  style: const TextStyle(fontSize: 18),
                ),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  backgroundColor: Colors.orangeAccent,
                  foregroundColor: Colors.white,
                ),
              ),
              if (_result.isNotEmpty) ...[
                const SizedBox(height: 24),
                const Divider(),
                const SizedBox(height: 8),
                const Text(
                  'ผลลัพธ์ (คัดลอกไปใช้ได้เลย):',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey[100],
                    border: Border.all(color: Colors.grey[300]!),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: SelectableText(
                    _result,
                    style: const TextStyle(fontSize: 16),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
