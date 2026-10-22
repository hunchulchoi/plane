/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useState } from "react";
import useSWR from "swr";
import { Button } from "@makeplane/propel/components/button";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { useTranslation } from "@plane/i18n";
import { ForgejoService } from "@/services/integrations/forgejo.service";
import type { TForgejoRepository } from "@/services/integrations/forgejo.service";
import { ProjectService } from "@/services/project";

const service = new ForgejoService();
const projectService = new ProjectService();

export function ForgejoIntegration({ workspaceSlug }: { workspaceSlug: string }) {
  const { t } = useTranslation();
  const {
    data: repositories,
    error: loadError,
    mutate,
  } = useSWR(["forgejo-repositories", workspaceSlug], () => service.list(workspaceSlug), { refreshInterval: 15000 });
  const { data: projects, error: projectError } = useSWR(["forgejo-projects", workspaceSlug], () =>
    projectService.getProjectsLite(workspaceSlug)
  );
  const [projectId, setProjectId] = useState("");
  const [url, setUrl] = useState("");
  const [created, setCreated] = useState<TForgejoRepository | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await service.connect(workspaceSlug, projectId, url.trim());
      setCreated(result);
      setUrl("");
      await mutate();
    } catch {
      setError(t("forgejo_integration.connect_error"));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async (id: string) => {
    if (!window.confirm(t("forgejo_integration.confirm_disconnect"))) return;
    setBusy(true);
    setError(null);
    try {
      await service.disconnect(workspaceSlug, id);
      if (created?.id === id) setCreated(null);
      await mutate();
    } catch {
      setError(t("forgejo_integration.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="flex flex-col gap-4 border-b border-subtle py-6" aria-labelledby="forgejo-heading">
      <h4 id="forgejo-heading" className="text-16 font-semibold">
        Forgejo
      </h4>
      <p className="text-13 text-secondary">{t("forgejo_integration.description")}</p>
      {(error || loadError || projectError) && (
        <p role="alert" className="text-13 text-danger-primary">
          {error ?? t("forgejo_integration.error")}
        </p>
      )}
      <form
        className="flex max-w-2xl flex-wrap items-center gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void connect();
        }}
      >
        <select
          aria-label={t("forgejo_integration.project")}
          className="rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13"
          value={projectId}
          disabled={busy || !projects}
          required
          onChange={(event) => setProjectId(event.target.value)}
        >
          <option value="">{t("forgejo_integration.project")}</option>
          {projects
            ?.filter((project) => project.member_role != null && !project.archived_at)
            .map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
        </select>
        <div className="min-w-64 flex-1">
          <InputGroup size="md">
            <Input
              size="md"
              type="url"
              aria-label={t("forgejo_integration.repository")}
              placeholder="https://forgejo.example.com/owner/repo"
              value={url}
              required
              disabled={busy}
              maxLength={500}
              onChange={(event) => setUrl(event.target.value)}
            />
          </InputGroup>
        </div>
        <Button
          type="submit"
          size="md"
          stretch="auto"
          variant="primary"
          label={t("forgejo_integration.connect")}
          disabled={busy || !projectId || !url.trim() || !!created}
          loading={busy}
        />
      </form>
      {created?.secret && (
        <div role="status" className="flex max-w-2xl flex-col gap-3 rounded-md border border-subtle p-4">
          <p className="text-13">{t("forgejo_integration.setup")}</p>
          <label className="text-13">
            {t("forgejo_integration.webhook_url")}
            <input
              className="mt-1 block w-full rounded border border-subtle bg-surface-1 p-2"
              readOnly
              value={created.webhook_url}
              onFocus={(event) => event.target.select()}
            />
          </label>
          <label className="text-13">
            {t("forgejo_integration.secret")}
            <input
              className="mt-1 block w-full rounded border border-subtle bg-surface-1 p-2"
              readOnly
              value={created.secret}
              onFocus={(event) => event.target.select()}
            />
          </label>
          <p className="text-13 text-secondary">{t("forgejo_integration.secret_notice")}</p>
          <Button
            size="sm"
            stretch="auto"
            variant="secondary"
            label={t("forgejo_integration.done")}
            onClick={() => setCreated(null)}
          />
        </div>
      )}
      {!repositories && !loadError && <p className="text-13">{t("integrations.loading")}</p>}
      {repositories?.length === 0 && <p className="text-13 text-secondary">{t("forgejo_integration.empty")}</p>}
      <ul className="flex flex-col gap-3">
        {repositories?.map((repo) => (
          <li
            key={repo.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-subtle p-3"
          >
            <div className="min-w-0 text-13">
              <p className="font-medium">{repo.project_name}</p>
              <a
                className="break-all text-accent-primary"
                href={repo.repository_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {repo.repository_url}
              </a>
              <p className="break-all text-secondary">
                {t("forgejo_integration.webhook_url")}: {repo.webhook_url}
              </p>
              <p className="text-secondary">
                {t("forgejo_integration.last_received")}:{" "}
                {repo.last_received_at
                  ? new Date(repo.last_received_at).toLocaleString()
                  : t("forgejo_integration.waiting")}
              </p>
            </div>
            <Button
              size="sm"
              stretch="auto"
              variant="secondary"
              label={t("forgejo_integration.disconnect")}
              disabled={busy}
              onClick={() => void disconnect(repo.id)}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
