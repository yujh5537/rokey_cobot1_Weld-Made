FROM python:3.12-slim

# 컨테이너 내부 작업 폴더
WORKDIR /app

# 필요한 Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# FastAPI 코드 복사
COPY . .

# FastAPI 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
