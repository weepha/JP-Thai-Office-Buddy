import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;

class VisionScreen extends StatefulWidget {
  const VisionScreen({super.key});

  @override
  State<VisionScreen> createState() => _VisionScreenState();
}

class _VisionScreenState extends State<VisionScreen> {
  File? _imageFile;
  XFile? _webImage;
  final _picker = ImagePicker();
  bool _isLoading = false;
  Map<String, dynamic>? _result;
  String? _error;

  Future<void> _pickImage(ImageSource source) async {
    try {
      final pickedFile = await _picker.pickImage(source: source);
      if (pickedFile != null) {
        setState(() {
          if (kIsWeb) {
            _webImage = pickedFile;
          } else {
            _imageFile = File(pickedFile.path);
          }
          _result = null;
          _error = null;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Error picking image: $e';
      });
    }
  }

  Future<void> _analyzeImage() async {
    if (_imageFile == null && _webImage == null) return;

    setState(() {
      _isLoading = true;
      _result = null;
      _error = null;
    });

    try {
      // For Chrome/Web use localhost (127.0.0.1)
      final url = Uri.parse('http://127.0.0.1:5000/vision_ocr');
      
      var request = http.MultipartRequest('POST', url);
      
      if (kIsWeb && _webImage != null) {
        request.files.add(
          http.MultipartFile.fromBytes(
            'image',
            await _webImage!.readAsBytes(),
            filename: _webImage!.name,
          ),
        );
      } else if (_imageFile != null) {
         request.files.add(
          await http.MultipartFile.fromPath(
            'image',
            _imageFile!.path,
          ),
        );
      }

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

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
      appBar: AppBar(title: const Text('แปลจากภาพ (Vision OCR)')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              height: 200,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey),
                borderRadius: BorderRadius.circular(12),
                color: Colors.grey[200],
              ),
              child: _imageFile == null && _webImage == null
                  ? const Center(child: Text('ยังไม่ได้เลือกรูปภาพ', style: TextStyle(fontSize: 16)))
                  : ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: kIsWeb 
                        ? Image.network(_webImage!.path, fit: BoxFit.cover)
                        : Image.file(_imageFile!, fit: BoxFit.cover),
                    ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                ElevatedButton.icon(
                  onPressed: _isLoading ? null : () => _pickImage(ImageSource.camera),
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('ถ่ายรูป'),
                ),
                ElevatedButton.icon(
                  onPressed: _isLoading ? null : () => _pickImage(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library),
                  label: const Text('เลือกจากเครื่อง'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: (_imageFile != null || _webImage != null) && !_isLoading ? _analyzeImage : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.indigo,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
              child: _isLoading
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : const Text('วิเคราะห์และแปล (Analyze)', style: TextStyle(fontSize: 18)),
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
                      const Text('ข้อความต้นฉบับ (ญี่ปุ่น):', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
                      SelectableText(_result!['original_text'] ?? '-', style: const TextStyle(fontSize: 16)),
                      const SizedBox(height: 12),
                      const Text('คำแปล (ไทย):', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.indigo)),
                      SelectableText(_result!['translated_text'] ?? '-', style: const TextStyle(fontSize: 18, color: Colors.black87)),
                      if (_result!['summary'] != null && _result!['summary'].isNotEmpty) ...[
                         const Divider(height: 24),
                         const Text('สรุปใจความสำคัญ:', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.teal)),
                         Text(_result!['summary'], style: const TextStyle(fontSize: 16)),
                      ]
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
