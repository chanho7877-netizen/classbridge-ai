import os, threading, queue, time, re, json, urllib.request, urllib.error
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import sounddevice as sd

# Keep downloaded AI models next to the executable (not inside PyInstaller temporary files).
import sys
BASE=os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
os.environ["HF_HOME"]=os.path.join(BASE,"models","huggingface")
os.environ["XDG_CACHE_HOME"]=os.path.join(BASE,"models","cache")
os.makedirs(os.path.join(BASE,"models"),exist_ok=True)
MODEL_NAME="facebook/nllb-200-distilled-600M"
LANG={"한국어 → 러시아어":("ko","kor_Hang","rus_Cyrl"),
      "러시아어 → 한국어":("ru","rus_Cyrl","kor_Hang")}

class App:
    def __init__(self,root):
        self.root=root; root.title("ClassBridge AI — 무료 로컬 통역"); root.geometry("920x780")
        self.events=queue.Queue(); self.recording=False; self.frames=[]; self.stream=None
        self.busy=False; self.asr=None; self.tokenizer=None; self.translator=None
        self.history=[]; self.context_subject=tk.StringVar(value="자동 (최근 대화)"); self.context_topic=tk.StringVar(value="")
        self.explain=tk.BooleanVar(value=False); self.use_llm=tk.BooleanVar(value=False)
        self.autostop=tk.BooleanVar(value=True); self.ollama_model=tk.StringVar(value="qwen2.5:3b")
        self.direction=tk.StringVar(value="한국어 → 러시아어")
        self.speak=tk.BooleanVar(value=False)
        self.status=tk.StringVar(value="준비됨 · 최초 사용 시 모델 다운로드 필요 (수 GB)")
        f=ttk.Frame(root,padding=18); f.pack(fill="both",expand=True)
        ttk.Label(f,text="ClassBridge AI",font=("Arial",23,"bold")).pack(anchor="w")
        ttk.Label(f,text="초등학교 1~6학년 · 한국어 → 러시아어 · 무료 로컬 통역 + 수업 맥락").pack(anchor="w",pady=(2,10))
        ctx=ttk.LabelFrame(f,text="수업 맥락 (선택 사항)",padding=8);ctx.pack(fill="x",pady=3)
        ttk.Label(ctx,text="교과").grid(row=0,column=0,sticky="w")
        ttk.Combobox(ctx,textvariable=self.context_subject,values=["자동 (최근 대화)","국어","수학","사회","과학","미술","생활지도","기타"],state="readonly",width=17).grid(row=0,column=1,padx=5)
        ttk.Label(ctx,text="주제").grid(row=0,column=2,padx=4)
        ttk.Entry(ctx,textvariable=self.context_topic,width=36).grid(row=0,column=3,sticky="ew")
        ctx.columnconfigure(3,weight=1)
        ttk.Checkbutton(ctx,text="설명 모드 (러시아어로 쉬운 설명)",variable=self.explain).grid(row=1,column=0,columnspan=3,sticky="w",pady=5)
        ttk.Checkbutton(ctx,text="Ollama 문맥 AI 사용 (선택)",variable=self.use_llm).grid(row=2,column=0,columnspan=3,sticky="w")
        ttk.Label(ctx,text="Ollama 모델").grid(row=2,column=3,sticky="w")
        ttk.Entry(ctx,textvariable=self.ollama_model,width=18).grid(row=3,column=3,sticky="w")
        ttk.Checkbutton(ctx,text="침묵 1.2초 후 자동 녹음 종료",variable=self.autostop).grid(row=3,column=0,columnspan=3,sticky="w")
        bar=ttk.Frame(f);bar.pack(fill="x",pady=4)
        ttk.Label(bar,text="통역 방향:").pack(side="left")
        ttk.Combobox(bar,textvariable=self.direction,values=list(LANG),state="readonly",width=24).pack(side="left",padx=8)
        ttk.Checkbutton(bar,text="Windows 음성으로 읽기 (해당 언어 음성 설치 필요)",variable=self.speak).pack(side="left")
        buttons=ttk.Frame(f);buttons.pack(fill="x",pady=12)
        self.btn=ttk.Button(buttons,text="🎙 녹음 시작",command=self.toggle);self.btn.pack(side="left")
        ttk.Button(buttons,text="문맥 초기화",command=self.reset_context).pack(side="right")
        ttk.Button(buttons,text="입력 문장 번역",command=self.translate_text).pack(side="left",padx=10)
        ttk.Button(buttons,text="방향 바꾸기",command=self.swap).pack(side="left")
        ttk.Label(f,text="원문 (직접 입력하거나 마이크로 녹음)",font=("Arial",11,"bold")).pack(anchor="w",pady=(12,4))
        self.src=tk.Text(f,height=7,wrap="word",font=("Arial",12));self.src.pack(fill="both",expand=True)
        ttk.Label(f,text="번역",font=("Arial",11,"bold")).pack(anchor="w",pady=(14,4))
        self.dst=tk.Text(f,height=7,wrap="word",font=("Arial",12));self.dst.pack(fill="both",expand=True)
        ttk.Label(f,textvariable=self.status,wraplength=790).pack(anchor="w",pady=12)
        ttk.Label(f,text="개인정보 보호: 녹음은 임시 처리 후 삭제 · API 키 불필요 · 자동 저장 없음",foreground="#555").pack(anchor="w")
        root.after(100,self.poll)
        root.protocol("WM_DELETE_WINDOW",self.close)
    def emit(self,kind,data): self.events.put((kind,data))
    def poll(self):
        while not self.events.empty():
            kind,data=self.events.get()
            if kind=="status":self.status.set(data)
            elif kind=="source":self.src.delete("1.0","end");self.src.insert("1.0",data)
            elif kind=="target":self.dst.delete("1.0","end");self.dst.insert("1.0",data)
            elif kind=="done":self.busy=False;self.btn.config(state="normal")
            elif kind=="error":messagebox.showerror("오류",data)
        self.root.after(100,self.poll)
    def reset_context(self):
        self.history.clear();self.status.set("이전 발화 문맥을 초기화했습니다.")
    def swap(self):
        self.direction.set(next(k for k in LANG if k!=self.direction.get()))
    def toggle(self):
        if self.busy:return
        if not self.recording:
            try:
                self.frames=[]
                self.last_voice=time.monotonic();self.heard_voice=False
                self.stream=sd.InputStream(samplerate=16000,channels=1,dtype="float32",
                                           callback=self.audio_callback)
                self.stream.start();self.recording=True
                self.btn.config(text="■ 녹음 종료 및 통역")
                self.status.set("녹음 중… 침묵 자동 종료를 사용하거나 종료 버튼을 누르세요.")
                self.root.after(250,self.check_silence)
            except Exception as e:messagebox.showerror("마이크 오류",str(e))
        else:
            self.recording=False;self.stream.stop();self.stream.close();self.stream=None
            self.btn.config(text="🎙 녹음 시작",state="disabled")
            audio=np.concatenate(self.frames,axis=0).flatten() if self.frames else np.array([])
            self.busy=True
            direction=self.direction.get()
            threading.Thread(target=self.process_audio,args=(audio,direction),daemon=True).start()
    def audio_callback(self,data,frames,t,status):
        if not self.recording:return
        self.frames.append(data.copy())
        rms=float(np.sqrt(np.mean(data*data)))
        if rms>0.018:self.last_voice=time.monotonic();self.heard_voice=True
    def check_silence(self):
        if not self.recording:return
        if self.autostop.get() and self.heard_voice and time.monotonic()-self.last_voice>1.2:
            self.toggle();return
        self.root.after(250,self.check_silence)
    def translate_text(self):
        if self.busy or self.recording:return
        source=self.src.get("1.0","end").strip()
        if not source:return
        self.busy=True;self.btn.config(state="disabled")
        threading.Thread(target=self.process_text,args=(source,self.direction.get()),daemon=True).start()
    def load_asr(self):
        if self.asr is None:
            from faster_whisper import WhisperModel
            self.emit("status","음성 인식 모델 준비 중… (첫 실행에는 다운로드)")
            self.asr=WhisperModel("small",device="cpu",compute_type="int8",
                                  download_root=os.path.join(BASE,"models","whisper"))
    def load_translation(self):
        if self.translator is None:
            from transformers import AutoTokenizer,AutoModelForSeq2SeqLM
            self.emit("status","NLLB 번역 모델 준비 중… (첫 실행에는 다운로드)")
            self.tokenizer=AutoTokenizer.from_pretrained(MODEL_NAME)
            self.translator=AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
            self.translator.eval()
    def process_audio(self,audio,direction):
        try:
            if len(audio)<4000:raise ValueError("녹음이 너무 짧습니다.")
            self.load_asr()
            self.emit("status","음성 인식 중…")
            lang,_,_=LANG[direction]
            segments,_=self.asr.transcribe(audio,language=lang,beam_size=3,vad_filter=True)
            source=" ".join(s.text.strip() for s in segments).strip()
            if not source:raise ValueError("음성을 인식하지 못했습니다. 마이크와 소음을 확인하세요.")
            self.emit("source",source)
            self.do_translate(source,direction)
        except Exception as e:self.emit("error",str(e));self.emit("status","오류 발생")
        finally:self.emit("done",None)
    def process_text(self,source,direction):
        try:self.do_translate(source,direction)
        except Exception as e:self.emit("error",str(e));self.emit("status","오류 발생")
        finally:self.emit("done",None)
    def ollama_generate(self,source,direction):
        subject=self.context_subject.get()
        topic=self.context_topic.get().strip()
        context="\n".join("교사: "+a+"\n러시아어: "+b for a,b in self.history[-5:])
        instruction=("초등학생이 이해할 수 있도록 러시아어로 개념을 짧고 정확하게 설명하세요. "
                     "교사가 요청한 개념만 설명하고 불확실하면 추측하지 마세요." if self.explain.get() else
                     "한국어를 러시아어로 정확히 통역하세요. 원문의 질문/지시/감정을 보존하고 "
                     "임의로 내용을 추가하거나 학생에게 답하지 마세요. 러시아어 번역만 출력하세요.")
        prompt=f"{instruction}\n교과: {subject}\n수업 주제: {topic or '자동'}\n최근 발화 참고(내용을 임의로 추가하지 말 것):\n{context}\n현재 한국어 발화: {source}\n러시아어 출력:"
        body=json.dumps({"model":self.ollama_model.get().strip(),"prompt":prompt,"stream":False,
                         "options":{"temperature":0.1,"num_predict":220}},ensure_ascii=False).encode('utf-8')
        req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=body,
                                   headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=180) as response:
            result=json.loads(response.read().decode('utf-8'))
        answer=result.get('response','').strip()
        if not answer:raise RuntimeError('Ollama가 빈 답변을 반환했습니다.')
        return answer
    def do_translate(self,source,direction):
        if self.explain.get() and not self.use_llm.get():
            self.emit("status","설명 모드는 Ollama 문맥 AI를 켜야 합니다. 현재는 일반 통역으로 진행합니다.")
        if self.use_llm.get() and direction=="한국어 → 러시아어":
            self.emit("status","Ollama가 최근 발화와 수업 주제를 참고해 통역 중…")
            try:translated=self.ollama_generate(source,direction)
            except Exception as e:
                self.emit("status","Ollama 연결 실패 · 기본 번역 모델로 대체: "+str(e))
                translated=self.nllb_translate(source,direction)
        else:
            translated=self.nllb_translate(source,direction)
        self.history.append((source,translated))
        self.history=self.history[-10:]
        self.emit("target",translated)
        self.emit("status","완료 · 최근 발화 "+str(len(self.history))+"개를 메모리에 유지 중 (프로그램 종료 시 삭제)")
        if self.speak.get():
            try:
                import pyttsx3
                engine=pyttsx3.init()
                language_prefix="ru" if direction=="한국어 → 러시아어" else "ko"
                voices=engine.getProperty("voices")
                matching=[v for v in voices if language_prefix in
                          (str(v.id)+" "+str(v.name)+" "+str(getattr(v,"languages",[]))).lower()]
                if matching:
                    engine.setProperty("voice",matching[0].id)
                    engine.say(translated);engine.runAndWait()
                else:self.emit("status","번역 완료 · Windows에 해당 언어 음성이 설치되지 않았습니다.")
                engine.stop()
            except Exception as e:self.emit("status","번역 완료 · 음성 출력 실패: "+str(e))
    def nllb_translate(self,source,direction):
        self.load_translation()
        import torch
        _,src,tgt=LANG[direction]
        self.tokenizer.src_lang=src
        self.emit("status","NLLB 번역 중…")
        chunks=[];words=source.split()
        for i in range(0,len(words),75):chunks.append(" ".join(words[i:i+75]))
        output=[]
        for chunk in chunks:
            inp=self.tokenizer(chunk,return_tensors="pt",truncation=True,max_length=256)
            with torch.inference_mode():
                ids=self.translator.generate(**inp,forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(tgt),
                                             max_new_tokens=256,num_beams=3)
            output.append(self.tokenizer.batch_decode(ids,skip_special_tokens=True)[0])
        return " ".join(output)
    def close(self):
        if self.stream:
            try:self.stream.stop();self.stream.close()
            except Exception:pass
        self.root.destroy()

if __name__=="__main__":
    root=tk.Tk()
    try:
        style=ttk.Style(root)
        if "vista" in style.theme_names():style.theme_use("vista")
    except Exception:pass
    App(root);root.mainloop()
