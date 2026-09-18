# ==============================
# 1단계: Spring Boot 빌드
# ==============================
FROM gradle:8-jdk21 AS builder

WORKDIR /app

# 프로젝트 파일 복사
COPY . .

# Spring Boot 실행 JAR 생성
RUN gradle bootJar --no-daemon


# ==============================
# 2단계: 실제 서버 실행
# ==============================
FROM eclipse-temurin:21-jre

WORKDIR /app

# 빌드된 JAR 파일 복사
COPY --from=builder /app/build/libs/*.jar app.jar

# Spring Boot 실행
CMD ["java", "-jar", "app.jar"]
