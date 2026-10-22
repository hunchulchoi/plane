/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { Button } from "@makeplane/propel/components/button";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { useTranslation } from "@plane/i18n";
import { PasskeyService, supportsPasskeys } from "@/services/passkey.service";
import type { TPasskey } from "@/services/passkey.service";

const service = new PasskeyService();

export function PasskeySettings() {
  const { t } = useTranslation();
  const [keys, setKeys] = useState<TPasskey[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [supported, setSupported] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setSupported(supportsPasskeys());
    void service
      .list()
      .then((data) => {
        if (active) setKeys(data);
        return data;
      })
      .catch(() => {
        if (active) setError(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const register = async () => {
    setBusy(true);
    setError(false);
    try {
      await service.register(name.trim());
      setKeys(await service.list());
      setName("");
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm(t("auth.passkeys.confirm_delete"))) return;
    setBusy(true);
    setError(false);
    try {
      await service.remove(id);
      setKeys((current) => current.filter((key) => key.id !== id));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-labelledby="passkeys-heading"
      className="mt-10 flex max-w-xl flex-col gap-4 border-t border-subtle pt-6"
    >
      <h2 id="passkeys-heading" className="text-18 font-semibold">
        {t("auth.passkeys.title")}
      </h2>
      <p className="text-13 text-secondary">{t("auth.passkeys.description")}</p>
      {!supported && <p className="text-13 text-secondary">{t("auth.passkeys.unsupported")}</p>}
      {error && (
        <p role="alert" className="text-13 text-danger-primary">
          {t("auth.passkeys.error")}
        </p>
      )}
      {loading ? (
        <p>{t("auth.passkeys.loading")}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {keys.map((key) => (
            <li key={key.id} className="flex items-center justify-between gap-3">
              <span className="truncate text-13">{key.name}</span>
              <Button
                variant="secondary"
                size="sm"
                stretch="auto"
                label={t("auth.passkeys.delete")}
                disabled={busy}
                onClick={() => void remove(key.id)}
              />
            </li>
          ))}
          {keys.length === 0 && <li className="text-13 text-secondary">{t("auth.passkeys.empty")}</li>}
        </ul>
      )}
      <form
        className="flex items-center gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void register();
        }}
      >
        <div className="flex-1">
          <InputGroup size="md">
            <Input
              size="md"
              aria-label={t("auth.passkeys.name")}
              placeholder={t("auth.passkeys.name")}
              value={name}
              maxLength={100}
              required
              disabled={busy || !supported}
              onChange={(event) => setName(event.target.value)}
            />
          </InputGroup>
        </div>
        <Button
          type="submit"
          variant="primary"
          size="md"
          stretch="auto"
          label={t("auth.passkeys.add")}
          loading={busy}
          disabled={busy || !supported || !name.trim()}
        />
      </form>
    </section>
  );
}
