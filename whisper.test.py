from transformers import WhisperProcessor, WhisperForConditionalGeneration 
from datasets import load_dataset 
import torch
import evaluate 
import re 
# LANGUAGES: en(english), zh(chinese), ko(korean), ja(japanese) 


class MyWhisper:
    def __init__(self, processor, model, *args):
        # init model and processor for conditional generation 
        self.processor = processor 
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = model.to(self.device)
        
    def predict_transcription(self, input_features):
        predicted_ids = self.model.generate(input_features)
        transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)
        return transcription
            
        
    def main(self, **kwargs): 
        audio_arraies = kwargs.pop("audio_arraies", [])
        if not audio_arraies:
            raise ValueError("audio arraies are empty")
        predictions = []
        for array in audio_arraies:
            input_features = self.processor(array, sampling_rate = 16_000, return_tensor="pt").input_features().to(self.device)
            prediction = self.predict_transcription(input_features)
            predictions.append(prediction)
        return predictions

    
if __name__ == "__main__":
    import argparse 
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="repo/model_name")
    parser.add_argument("--language", help="english, korean, chinese, japanese")
    parser.add_argument("--dataset_name", help="repo/dataset_name")
    parser.add_argument("--metric", help="wer for english / cer for korean, japanese, chinese")
    args = parser.parse_args()
    
    # 1. get the model and processor and initialize MyWhisper 
    processor = WhisperProcessor.from_pretrained(args.model)
    model = WhisperForConditionalGeneration.from_pretrained(args.model)
    model.config.forced_decoder_ids = WhisperProcessor.get_decoder_prompt_ids(language=args.language, task="transcribe")
    whisperer = MyWhisper(processor=processor, model=model)
    
    # 2. load the dataset in streaming mode since we don't need the whole dataset. 
    ds = load_dataset(args.dataset_name, "en_us", split="train", streaming="true", trust_remote_code=True)
    transcriptions = []
    audio_arraies = []    
    count = 0
    for cur in iter(ds):
        count += 1
        try:
            transcriptions.append(cur['transcription'])
            audio_arraies.append(cur["audio"]["array"])
        except Exception as e:
            print(e)
        if count > 100:
            break 
    
    # 3. generate predictions and make some post processing. 
    predictions = whisperer.main(transcriptions = transcriptions, audio_arraies = audio_arraies)
    def post_processing(x):
        x = re.sub("[.,?!']", "", x)
        return x 
    
    
    predictions = list(map(lambda x: x[0], predictions))
    predictions = list(map(post_processing, predictions))
    transcriptions = list(map(post_processing, transcriptions))
    # 4. load the metric to compute 
    metric = evaluate.load(args.metric) 
    with open("./scores.txt", mode="w", encoding="utf-8") as f:
        for ref, pred in zip(transcriptions, predictions):
            try:
                score = metric.compute(predictions = [pred], references=[ref])
                f.write(f"{pred} :: {ref} :: {round(score, 2)}\n")
            except Exception as e:
                print(e)
                continue