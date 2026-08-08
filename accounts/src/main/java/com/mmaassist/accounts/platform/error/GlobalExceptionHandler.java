package com.mmaassist.accounts.platform.error;

import java.net.URI;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.MethodArgumentNotValidException;

/** Renders every error as RFC 9457 {@code application/problem+json}. */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    public ProblemDetail handleApiException(ApiException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(ex.getStatus(), ex.getMessage());
        problem.setType(URI.create("urn:mmaassist:error:" + ex.getCode()));
        problem.setProperty("code", ex.getCode());
        ex.getProperties().forEach(problem::setProperty);

        // 4xx is the client's problem and is logged at debug; 5xx is ours.
        if (ex.getStatus().is5xxServerError()) {
            log.error("api error {}: {}", ex.getCode(), ex.getMessage(), ex);
        } else {
            log.debug("api error {}: {}", ex.getCode(), ex.getMessage());
        }
        return problem;
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.BAD_REQUEST, "The request body failed validation.");
        problem.setType(URI.create("urn:mmaassist:error:invalid_request"));
        problem.setProperty("code", "invalid_request");
        problem.setProperty("fields", ex.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .toList());
        return problem;
    }

    @ExceptionHandler(Exception.class)
    public ProblemDetail handleUnexpected(Exception ex) {
        // The message may name a table, a Stripe object, or a query. Log it,
        // never return it.
        log.error("unhandled exception", ex);
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(
                HttpStatus.INTERNAL_SERVER_ERROR, "Something went wrong on our side.");
        problem.setType(URI.create("urn:mmaassist:error:internal"));
        problem.setProperty("code", "internal");
        return problem;
    }
}
