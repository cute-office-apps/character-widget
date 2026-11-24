# 캐릭터 위젯

Windows와 macOS 바탕화면에 내가 고른 그림이 캐릭터로 떠 있는 위젯이에요.

- 캐릭터를 클릭하면 메모가 열려요 (Windows 스티커 메모 연동, Mac은 위젯 메모장)
- 구글 캘린더를 연결하면 오늘 일정과 일정 10분 전을 말풍선으로 알려줘요
- 봄·여름·가을·겨울·크리스마스 테마로 캐릭터를 꾸밀 수 있어요
- 캐릭터 그림은 직접 등록해요. 움직이는 GIF도 재생해요.

## Mac에 설치하기

1. Mac용 zip 압축을 풀고 `CharacterWidget.app`을 **응용 프로그램** 폴더로 옮겨 더블클릭해요. Python은 앱에 들어 있어요.
2. **캐릭터를 등록해 주세요!**를 누르고 그림을 고르세요.
3. 트랙패드 두 손가락 클릭 또는 Control-클릭으로 메뉴를 열어요. 로그인할 때 시작하려면 메뉴의 **로그인 시 자동 실행 설정**을 누르고 로그인 항목에 앱을 추가하세요.

새 버전은 앱을 종료한 후 응용 프로그램 폴더의 `.app`을 교체해 설치해요. 메모, 그림, 설정은 `~/Library/Application Support/CharacterWidget`에 저장돼요. 앱을 제거하려면 로그인 항목에서 빼고 `.app`을 휴지통으로 옮기세요.

캐릭터와 소품에 PNG, GIF, JPG/JPEG, HEIC/HEIF, WebP, AVIF, BMP, TIFF를 가져올 수 있어요 (Windows는 1.6부터). PNG·GIF가 아닌 그림은 PNG로 바꿔서 저장하고, 사진 방향도 바로잡아요. 움직이는 WebP나 AVIF는 첫 프레임을 표시해요.
Windows에서 HEIC·HEIF·WebP·AVIF는 Microsoft Store의 'HEIF 이미지 확장', 'WebP 이미지 확장', 'AV1 비디오 확장'이 있어야 열려요.

## Windows용 내려받기

**[간편판 내려받기 (Python 설치 필요 없음, 추천)](https://github.com/cute-office-apps/character-widget/raw/main/CharacterWidget_v1.0_Easy.zip)** · 약 14MB

[기본판 내려받기 (Python을 직접 설치해서 쓰는 버전)](https://github.com/cute-office-apps/character-widget/raw/main/CharacterWidget_v1.0.zip) · 약 0.2MB

## Windows 설치 방법 (간편판)

1. 받은 zip 파일을 우클릭 → **압축 풀기** (꼭 먼저 풀어 주세요)
2. 풀린 폴더 안의 **설치하기**를 더블클릭 → [설치하기] → [지금 실행하기]
   (파랑·노랑 뱀 모양 아이콘이에요. 공식 Python 프로그램이라 이 모양이에요.)
3. 바탕화면에 "캐릭터 위젯" 바로가기가 생겨요. 다음부터는 이걸 누르면 돼요.

간편판에는 [python.org](https://www.python.org)의 공식 Python이 고치지 않은 그대로 들어 있어요.

## Windows 설치 방법 (기본판)

1. **Python 설치 (처음 한 번)**
   시작 메뉴 → Microsoft Store → "Python 3.13" 검색 → 개발사 "Python Software Foundation" 확인 → 받기
   (이미 Python이 있으면 건너뛰세요)
2. 받은 zip 파일을 우클릭 → **압축 풀기**
3. 풀린 폴더 안의 **설치하기**를 더블클릭 → [설치하기] → [지금 실행하기]
4. 바탕화면에 "캐릭터 위젯" 바로가기가 생겨요. 다음부터는 이걸 누르면 돼요.

"설치하기"를 더블클릭해도 반응이 없으면:
"설치하기" 우클릭 → 연결 프로그램 → Python 선택 ("항상 이 앱 사용" 체크)

자세한 사용법은 zip 안의 `사용설명서.txt`를 봐 주세요.

## 사용법

| 동작 | 기능 |
|---|---|
| 클릭 | 메모 열기 |
| 드래그 | 위치 옮기기 |
| 우클릭 | 메뉴 (메모 / 오늘 일정 / 꾸미기 / 캐릭터 바꾸기 / 설정 / 사용법 보기 / 캐릭터 랜덤으로 바꾸기 / 자동 실행 / 다시 시작 / 끄기) |
| 캐릭터 랜덤으로 바꾸기 | 켜두면 켤 때마다, 그리고 30분마다 다른 캐릭터로 바뀌어요 (캐릭터 2개 이상) |
| ↻ 버튼 / F5 | 지금 바로 다른 캐릭터로 바꾸기 (우클릭 메뉴의 랜덤 줄) |
| 말풍선 클릭 | 말풍선 닫기 |

## Windows 업데이트 / 제거

- 자동 업데이트 (1.1부터): 새 버전이 나오면 캐릭터가 말풍선으로 알려줘요 → [업데이트] 한 번이면 끝 (내 메모·캐릭터·설정은 그대로 남아요)
- 직접 업데이트: 새 zip을 받아 압축 풀고 "설치하기" → [업데이트하기]
- 1.0을 쓰고 있다면 한 번만 직접 업데이트해 주세요. 그다음부터는 자동으로 알려줘요.
- 제거: "설치하기" → [제거하기]

## 안내

- Windows 10/11과 macOS에서 쓸 수 있어요.
- 구글 캘린더는 설정에 넣은 주소에서 일정을 **읽기만** 해요. 다른 곳으로 보내는 정보는 없어요.
- 캘린더 비공개 주소는 비밀번호와 같아요. 다른 사람에게 보내지 마세요.
- 다른 사람이 그린 그림이나 캐릭터는 개인적으로만 쓰고, 다시 퍼뜨리지 마세요.
- 소품·아이콘 그림은 이 위젯을 위해 새로 그린 오리지널이에요.

## Windows 새 버전 올리는 법 (관리자용)

1. `app/start_widget.pyw`의 `APP_VERSION`만 올려요 (예: 1.5 → 1.6)
2. `python3 tools/build_zips.py`를 실행해요
   - zip 두 개, `update.json`(버전·zip 크기·SHA-256), `version.txt`를 한 번에 새로 만들어요
   - `app/settings.ini`에 캘린더 주소(`ICAL_URL…`)나 `UPDATE_BASE` 값이 있으면 빌드가 멈춰요
3. 브랜치에 올리고 PR → 리뷰 → main에 병합해요 (main에 바로 올리지 않기)

main의 `update.json`이 바뀌면, 설치된 위젯(1.5 이상)이 6시간 안에 알아채고 사용자에게 물어봐요.
위젯은 받은 zip의 크기·SHA-256·버전이 `update.json`과 모두 같을 때만 설치하고, 설치 중 실패하면 원래 파일로 되돌려요.
1.1~1.4 설치본은 `version.txt`와 `CharacterWidget_v1.0.zip`을 읽으니 두 파일도 계속 둬요.
이 저장소에 올라간 내용은 사용자 PC에서 실행되니까, 올리기 전에 꼭 직접 테스트해 주세요.

## Mac용 앱 빌드하기

Tk가 포함된 Python으로 Mac에서 `python3 -m pip install pyinstaller`와 `python3 tools/build_macos.py`를 차례로 실행하세요. 기본 빌드는 실행하는 Python과 같은 CPU용이며, Universal 2 Python에서는 `--arch universal2`로 Apple Silicon과 Intel용을 하나로 묶을 수 있어요. 결과 zip은 `dist/`에 생겨요.
