# ClassBridge AI — GitHub 자동 빌드

이 프로젝트는 Windows용 포터블 실행파일을 GitHub Actions에서 빌드합니다.
**현재 ZIP에는 완성된 exe가 없습니다.** GitHub 빌드가 성공해야 다운로드할 수 있습니다.

## 시작하기 (PC에 Python 설치 불필요)
1. github.com/new 접속 → Repository name: `classbridge-ai` → Public 또는 Private → Create repository.
2. 저장소의 `Add file` → `Upload files`를 클릭.
3. ZIP을 먼저 압축 해제한 뒤 `app.py`, `requirements.txt`와 `.github/workflows/build-windows.yml`을 업로드합니다.
   주의: GitHub 웹 업로드에서 숨김 폴더 `.github`가 누락될 수 있습니다.
   누락 시 `Add file` → `Create new file` → 파일 이름 `.github/workflows/build-windows.yml`을 입력하고
   ZIP 안의 워크플로 내용을 붙여넣어 Commit 합니다.
4. 저장소 상단 Actions → `Build ClassBridge AI for Windows` → Run workflow → Run workflow.
5. 빌드가 성공(초록 체크)하면 해당 실행 내 `Artifacts`에서 `ClassBridgeAI-Windows-Portable` 다운로드.
6. 압축을 풀고 **폴더 전체**를 유지한 채 `ClassBridgeAI.exe` 실행.

## 최초 실행
- 무료 AI 모델은 첫 사용 시 수 GB 다운로드됩니다. 인터넷 연결이 필요합니다.
- 모델을 내려받은 후에는 로컬 번역이 가능합니다.
- 번역 음성은 Windows 해당 언어 음성 엔진 설치 여부에 따라 동작합니다.
- 문맥 추론/설명 모드는 별도 Ollama 및 모델 설치가 필요합니다.
- API 키나 OpenAI API 비용은 없습니다.

## 한계 및 주의
- 자동 빌드가 실제 PC의 마이크, 음성 출력, 번역 정확도를 검증하는 것은 아닙니다.
- Windows 백신이 서명 없는 앱에 경고할 수 있습니다. 경고를 무조건 무시하지 마세요.
- 빌드 과정에서 외부 Python 패키지를 설치하므로 종속성 공급망 위험이 있습니다.
- NLLB 모델의 비상업적 라이선스 및 사용 조건을 확인하세요.
- 학생의 음성을 다루므로 학교 개인정보 정책을 확인하세요.
- 공개 저장소에 학생 개인정보, API 키, 녹음 파일을 업로드하지 마세요.
- 처음에는 개인 PC에서 테스트하세요.
