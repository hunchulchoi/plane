/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import { AuthService } from "@/services/auth.service";

export type TPasskey = { id: string; name: string; created_at: string; last_used_at: string | null };

type DescriptorJSON = Omit<PublicKeyCredentialDescriptor, "id"> & { id: string };
type CreationJSON = Omit<PublicKeyCredentialCreationOptions, "challenge" | "user" | "excludeCredentials"> & {
  challenge: string;
  user: Omit<PublicKeyCredentialUserEntity, "id"> & { id: string };
  excludeCredentials?: DescriptorJSON[];
};
type RequestJSON = Omit<PublicKeyCredentialRequestOptions, "challenge" | "allowCredentials"> & {
  challenge: string;
  allowCredentials?: DescriptorJSON[];
};

export const supportsPasskeys = () =>
  typeof window !== "undefined" && window.isSecureContext && "PublicKeyCredential" in window;

function decode(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from(atob(base64), (char) => char.charCodeAt(0)).buffer;
}

function encode(value: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(value)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function descriptor(value: DescriptorJSON): PublicKeyCredentialDescriptor {
  return { ...value, id: decode(value.id) };
}

export class PasskeyService extends APIService {
  private authService = new AuthService();

  constructor() {
    super(API_BASE_URL);
  }

  private async csrfHeaders() {
    const { csrf_token } = await this.authService.requestCSRFToken();
    if (!csrf_token) throw new Error("CSRF token unavailable");
    return { "X-CSRFTOKEN": csrf_token };
  }

  async list(): Promise<TPasskey[]> {
    const response = await this.get("/auth/passkeys/");
    return response.data;
  }

  async remove(id: string): Promise<void> {
    const headers = await this.csrfHeaders();
    await this.delete(`/auth/passkeys/${id}/`, undefined, { headers });
  }

  async register(name: string): Promise<void> {
    const headers = await this.csrfHeaders();
    const { data } = await this.post("/auth/passkeys/register/options/", {}, { headers });
    const options = data as CreationJSON;
    const credential = await navigator.credentials.create({
      publicKey: {
        ...options,
        challenge: decode(options.challenge),
        user: { ...options.user, id: decode(options.user.id) },
        excludeCredentials: options.excludeCredentials?.map(descriptor),
      },
    });
    if (!(credential instanceof PublicKeyCredential)) throw new Error("Passkey registration cancelled");
    const response = credential.response as AuthenticatorAttestationResponse;
    await this.post(
      "/auth/passkeys/register/verify/",
      {
        name,
        credential: {
          id: credential.id,
          rawId: encode(credential.rawId),
          type: credential.type,
          response: {
            clientDataJSON: encode(response.clientDataJSON),
            attestationObject: encode(response.attestationObject),
            transports: response.getTransports?.() ?? [],
          },
          clientExtensionResults: credential.getClientExtensionResults(),
        },
      },
      { headers }
    );
  }

  async signIn(): Promise<string> {
    const headers = await this.csrfHeaders();
    const { data } = await this.post("/auth/passkeys/login/options/", {}, { headers });
    const options = data as RequestJSON;
    const credential = await navigator.credentials.get({
      publicKey: {
        ...options,
        challenge: decode(options.challenge),
        allowCredentials: options.allowCredentials?.map(descriptor),
      },
    });
    if (!(credential instanceof PublicKeyCredential)) throw new Error("Passkey sign-in cancelled");
    const response = credential.response as AuthenticatorAssertionResponse;
    const result = await this.post(
      "/auth/passkeys/login/verify/",
      {
        credential: {
          id: credential.id,
          rawId: encode(credential.rawId),
          type: credential.type,
          response: {
            clientDataJSON: encode(response.clientDataJSON),
            authenticatorData: encode(response.authenticatorData),
            signature: encode(response.signature),
            userHandle: response.userHandle ? encode(response.userHandle) : null,
          },
          clientExtensionResults: credential.getClientExtensionResults(),
        },
      },
      { headers }
    );
    return result.data.redirect_url;
  }
}
