package com.weldmade.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;


/*
 * Spring Boot 서버의 시작 클래스
 *
 * main()이 실행되면
 * Spring Boot 웹 서버가 시작된다.
 */
@SpringBootApplication
public class WeldMadeApplication {

    public static void main(String[] args) {
        SpringApplication.run(WeldMadeApplication.class, args);
    }
}
