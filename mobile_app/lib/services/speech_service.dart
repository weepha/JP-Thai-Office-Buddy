import 'package:speech_to_text/speech_to_text.dart';
import 'package:permission_handler/permission_handler.dart';

class SpeechService {
  final SpeechToText _speech = SpeechToText();
  bool _isInitialized = false;

  bool get isListening => _speech.isListening;

  Future<bool> initSpeech() async {
    // Request microphone permission first
    var status = await Permission.microphone.status;
    if (!status.isGranted) {
      status = await Permission.microphone.request();
      if (!status.isGranted) {
        return false;
      }
    }

    _isInitialized = await _speech.initialize(
      onError: (val) => print('Speech Error: $val'),
      onStatus: (val) => print('Speech Status: $val'),
    );
    return _isInitialized;
  }

  Future<void> startListening({
    required Function(String) onResult,
    String localeId = 'ja_JP', // Default to Japanese
  }) async {
    if (!_isInitialized) {
      bool allowed = await initSpeech();
      if (!allowed) return;
    }

    await _speech.listen(
      onResult: (val) => onResult(val.recognizedWords),
      localeId: localeId,
      listenFor: Duration(seconds: 30),
      cancelOnError: true,
      partialResults: true,
    );
  }

  Future<void> stopListening() async {
    await _speech.stop();
  }
}
