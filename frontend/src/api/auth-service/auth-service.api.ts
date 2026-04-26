import { openHands } from "../open-hands-axios";
import { AuthenticateResponse, GitHubAccessTokenResponse } from "./auth.types";
import { WebClientConfig } from "../option-service/option.types";

/**
 * Authentication service for handling all authentication-related API calls
 */
class AuthService {
  /**
   * Authenticate with GitHub token
   * @param appMode The application mode (saas or oss)
   * @param googleAuthEnabled Whether Google auth is enabled (for OSS mode)
   * @returns Response with authentication status and user info if successful
   */
  static async authenticate(
    appMode: WebClientConfig["app_mode"],
    googleAuthEnabled?: boolean,
  ): Promise<boolean> {
    if (appMode === "oss") {
      if (googleAuthEnabled) {
        const { data } = await openHands.get("/api/v1/auth/cf/status");
        return data.authenticated === true;
      }
      return true;
    }

    // Just make the request, if it succeeds (no exception thrown), return true
    await openHands.post<AuthenticateResponse>("/api/authenticate");
    return true;
  }

  /**
   * Get GitHub access token from Keycloak callback
   * @param code Code provided by GitHub
   * @returns GitHub access token
   */
  static async getGitHubAccessToken(
    code: string,
  ): Promise<GitHubAccessTokenResponse> {
    const { data } = await openHands.post<GitHubAccessTokenResponse>(
      "/api/keycloak/callback",
      {
        code,
      },
    );
    return data;
  }

  /**
   * Logout user from the application
   * @param appMode The application mode (saas or oss)
   */
  static async logout(
    appMode: WebClientConfig["app_mode"],
    googleAuthEnabled?: boolean,
  ): Promise<void> {
    if (appMode === "oss" && googleAuthEnabled) {
      // Cloudflare Access handles logout; just redirect to clear session
      window.location.href = "/cdn-cgi/access/logout";
      return;
    }
    const endpoint =
      appMode === "saas" ? "/api/logout" : "/api/unset-provider-tokens";
    await openHands.post(endpoint);
  }
}

export default AuthService;
