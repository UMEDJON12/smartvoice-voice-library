import java.io.*;import java.nio.file.*;import com.microsoft.cognitiveservices.speech.*;import tts.smartvoice.ui.*;import org.json.*;
/** Real on-device Embedded Speech implementation on the GitHub Linux runner; never a cloud voice. */
public final class NativeMicrosoftSample {
 public static void main(String[] args)throws Exception{
  MultiVoicePack.Voice voice=null;for(MultiVoicePack.Voice v:MultiVoicePack.read(new File(args[0])))if(v.engine.equals("microsoft")&&v.code.equals(args[1]))voice=v;
  if(voice==null)throw new IOException("Selected Microsoft model not found");String[] parameters=voice.param.split("\n",-1);if(parameters.length<2||parameters[1].trim().startsWith("M$LICENSE"))throw new IOException("Original compatible model parameters required");
  String language=voice.locale.split("-")[0],text=language.equals("fa")?"سلام. این یک نمونه از صدای انتخاب شده است.":language.equals("ar")?"مرحباً. هذا نموذج للصوت المحدد.":language.equals("uz")?"Salom. Bu tanlangan ovozning namunasi.":language.equals("yue")?"你好，呢個係所選聲音嘅試聽示範。":language.equals("zh")||language.equals("cmn")?"你好。这是所选语音的试听示例。":language.equals("en")?"Hello. This is a sample of the selected voice.":language.equals("tr")?"Merhaba. Bu, seçilen sesin bir örneğidir.":language.equals("ja")?"こんにちは。これは選択した音声のサンプルです。":language.equals("ru")?"Здравствуйте. Это образец выбранного голоса.":null;
  if(text==null){System.out.println(new JSONObject().put("success",false).put("unavailable",true).put("reason","No reviewed sample text for this language"));return;}
  try(EmbeddedSpeechConfig config=EmbeddedSpeechConfig.fromPath(MultiVoicePack.within(voice.root,voice.folder).getPath())){
   config.setSpeechSynthesisVoice(parameters[0].trim(),parameters[1].trim());config.setSpeechSynthesisOutputFormat(SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm);
   try(SpeechSynthesizer synth=new SpeechSynthesizer(config,null)){
    String name=parameters[0].trim().replace("&","&amp;").replace("\"","&quot;").replace("<","&lt;");String ssml="<speak version=\"1.0\" xmlns=\"http://www.w3.org/2001/10/synthesis\" xml:lang=\""+voice.locale+"\"><voice name=\""+name+"\"><prosody rate=\"1.0\" pitch=\"+0%\">"+text+"</prosody></voice></speak>";
    try(SpeechSynthesisResult result=synth.SpeakSsml(ssml)){
     if(result.getReason()!=ResultReason.SynthesizingAudioCompleted){SpeechSynthesisCancellationDetails d=SpeechSynthesisCancellationDetails.fromResult(result);System.out.println(new JSONObject().put("success",false).put("errorCode",String.valueOf(d.getErrorCode())));return;}
     byte[] data=result.getAudioData();if(data.length<1000)throw new IOException("No audio");Files.write(Paths.get(args[2]),data);System.out.println(new JSONObject().put("success",true).put("sampleText",text).put("locale",voice.locale).put("code",voice.code).put("bytes",data.length));
    }
   }
  }
 }
}
