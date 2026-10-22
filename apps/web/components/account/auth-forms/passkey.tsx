/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { Button } from "@makeplane/propel/components/button";
import { useTranslation } from "@plane/i18n";
import { PasskeyService, supportsPasskeys } from "@/services/passkey.service";

const service = new PasskeyService();

export function PasskeyLoginButton() {
  const { t } = useTranslation();
  const [supported, setSupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  useEffect(() => setSupported(supportsPasskeys()), []);

  if (!supported) return null;

  const signIn = async () => {
    setBusy(true);
    setError(false);
    try {
      const url = await service.signIn();
      window.location.assign(url);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <Button
        variant="secondary"
        size="lg"
        stretch="full"
        type="button"
        label={t("auth.passkeys.sign_in")}
        loading={busy}
        disabled={busy}
        onClick={() => void signIn()}
      />
      {error && (
        <p role="alert" className="text-13 text-danger-primary">
          {t("auth.passkeys.sign_in_error")}
        </p>
      )}
    </div>
  );
}
