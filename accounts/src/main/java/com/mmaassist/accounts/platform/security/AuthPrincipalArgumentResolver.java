package com.mmaassist.accounts.platform.security;

import com.mmaassist.accounts.platform.error.ApiException;
import java.util.Optional;
import org.springframework.core.MethodParameter;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.context.request.RequestAttributes;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

/**
 * Injects the caller into controller methods.
 *
 * <p>A method that declares {@code AuthPrincipal} requires authentication and
 * gets a 401 without it. A method that declares
 * {@code Optional<AuthPrincipal>} works either way.
 */
@Component
public class AuthPrincipalArgumentResolver implements HandlerMethodArgumentResolver {

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return AuthPrincipal.class.equals(parameter.getParameterType())
                || isOptionalPrincipal(parameter);
    }

    @Override
    public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer mavContainer,
                                  NativeWebRequest webRequest, WebDataBinderFactory binderFactory) {
        Object attribute = webRequest.getAttribute(
                AuthenticationFilter.PRINCIPAL_ATTRIBUTE, RequestAttributes.SCOPE_REQUEST);
        AuthPrincipal principal = attribute instanceof AuthPrincipal p ? p : null;

        if (isOptionalPrincipal(parameter)) {
            return Optional.ofNullable(principal);
        }
        if (principal == null) {
            throw ApiException.unauthorized("Sign in to continue.");
        }
        return principal;
    }

    private boolean isOptionalPrincipal(MethodParameter parameter) {
        if (!Optional.class.equals(parameter.getParameterType())) {
            return false;
        }
        return AuthPrincipal.class.equals(parameter.nested().getNestedParameterType());
    }
}
