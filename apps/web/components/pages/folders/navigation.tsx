/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { observer } from "mobx-react";
import { sortBy } from "lodash-es";
import { Folder, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@makeplane/propel/components/button";
import {
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogHeading,
  DialogMain,
  DialogTitle,
} from "@makeplane/propel/components/dialog";
import { InputField } from "@makeplane/propel/components/input-field";
import { EUserPermissions } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { setToast } from "@plane/blocks/toast";
import type { TPageFolder } from "@plane/types";
import { cn } from "@plane/utils";
import { usePageFolders, pageFolderService } from "@/hooks/pages/use-page-folders";
import { usePageStore, EPageStoreType } from "@/hooks/store";
import { useUserPermissions } from "@/hooks/store/user";

export const PageFolderNavigation = observer(function PageFolderNavigation() {
  const { t } = useTranslation();
  const { folders, error: loadError, isLoading, mutate, workspaceSlug, projectId } = usePageFolders();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  const { canCurrentUserCreatePage, getPageById, getCurrentProjectPageIds } = usePageStore(EPageStoreType.PROJECT);
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const selectedFolder = searchParams.get("folder");
  const [dialog, setDialog] = useState<{ action: "create" | "rename" | "delete"; folder?: TPageFolder } | null>(null);
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const role = getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId);
  const canDelete = role === EUserPermissions.ADMIN;

  const folderLink = (folderId?: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (folderId) params.set("folder", folderId);
    else params.delete("folder");
    return `${pathname}?${params.toString()}`;
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!dialog || isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (dialog.action === "delete" && dialog.folder) {
        await pageFolderService.removeFolder(workspaceSlug, projectId, dialog.folder.id);
        for (const id of getCurrentProjectPageIds(projectId)) {
          const page = getPageById(id);
          if (page?.folder === dialog.folder.id) page.mutateProperties({ folder: null }, false);
        }
        await mutate(
          folders.filter((folder) => folder.id !== dialog.folder?.id),
          { revalidate: false }
        );
        if (selectedFolder === dialog.folder.id) router.replace(folderLink());
      } else {
        const folder =
          dialog.action === "rename" && dialog.folder
            ? await pageFolderService.renameFolder(workspaceSlug, projectId, dialog.folder.id, name.trim())
            : await pageFolderService.createFolder(workspaceSlug, projectId, name.trim());
        await mutate(
          sortBy([...folders.filter((item) => item.id !== folder.id), folder], (item) => item.name.toLowerCase()),
          { revalidate: false }
        );
        if (dialog.action === "create") router.replace(folderLink(folder.id));
      }
      setDialog(null);
    } catch (error) {
      console.error("Unable to save page folder", error);
      setToast({ type: "error", title: t("page_folders.error") });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <nav
        aria-label={t("page_folders.title")}
        className="flex max-h-48 shrink-0 flex-col gap-1 overflow-y-auto border-b border-subtle p-3 md:max-h-none md:w-56 md:border-r md:border-b-0"
      >
        <div className="mb-1 flex items-center justify-between px-2">
          <span className="text-13 font-medium text-secondary">{t("page_folders.title")}</span>
          {canCurrentUserCreatePage && (
            <button
              type="button"
              aria-label={t("page_folders.create")}
              className="rounded-sm p-1 hover:bg-layer-1"
              onClick={() => {
                setName("");
                setDialog({ action: "create" });
              }}
            >
              <Plus className="size-4" />
            </button>
          )}
        </div>
        <Link
          href={folderLink()}
          aria-current={!selectedFolder ? "page" : undefined}
          className={cn("rounded-sm px-2 py-1.5 text-13 hover:bg-layer-1", {
            "bg-layer-1 font-medium": !selectedFolder,
          })}
        >
          {t("page_folders.all_pages")}
        </Link>
        {isLoading && <span className="px-2 text-13 text-tertiary">{t("page_folders.loading")}</span>}
        {loadError && (
          <button type="button" className="px-2 text-left text-13 text-danger-primary" onClick={() => void mutate()}>
            {t("page_folders.retry")}
          </button>
        )}
        {folders.map((folder) => (
          <div
            key={folder.id}
            className={cn("flex items-center gap-1 rounded-sm hover:bg-layer-1", {
              "bg-layer-1": selectedFolder === folder.id,
            })}
          >
            <Link
              href={folderLink(folder.id)}
              aria-current={selectedFolder === folder.id ? "page" : undefined}
              className="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-13"
            >
              <Folder className="size-4 shrink-0 text-tertiary" />
              <span className="truncate" title={folder.name}>
                {folder.name}
              </span>
            </Link>
            {canCurrentUserCreatePage && (
              <button
                type="button"
                aria-label={`${t("page_folders.rename")}: ${folder.name}`}
                className="shrink-0 rounded-sm p-1 hover:bg-layer-2"
                onClick={() => {
                  setName(folder.name);
                  setDialog({ action: "rename", folder });
                }}
              >
                <Pencil className="size-3.5" />
              </button>
            )}
            {canDelete && (
              <button
                type="button"
                aria-label={`${t("page_folders.delete")}: ${folder.name}`}
                className="shrink-0 rounded-sm p-1 hover:bg-layer-2"
                onClick={() => setDialog({ action: "delete", folder })}
              >
                <Trash2 className="size-3.5" />
              </button>
            )}
          </div>
        ))}
      </nav>
      <Dialog
        open={!!dialog}
        onOpenChange={(open) => {
          if (!open && !isSubmitting) setDialog(null);
        }}
      >
        <DialogContent size="md">
          <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
            <DialogMain>
              <DialogHeader>
                <DialogHeading>
                  <DialogTitle>{t(`page_folders.${dialog?.action ?? "create"}`)}</DialogTitle>
                </DialogHeading>
              </DialogHeader>
              <DialogBody>
                {dialog?.action === "delete" ? (
                  <p className="text-13">{t("page_folders.delete_description", { name: dialog.folder?.name ?? "" })}</p>
                ) : (
                  <InputField
                    id="page-folder-name"
                    size="md"
                    orientation="vertical"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={t("page_folders.name")}
                    aria-label={t("page_folders.name")}
                    maxLength={255}
                    required
                    disabled={isSubmitting}
                  />
                )}
              </DialogBody>
            </DialogMain>
            <DialogActions>
              <Button
                variant="secondary"
                size="md"
                stretch="auto"
                label={t("page_folders.cancel")}
                disabled={isSubmitting}
                onClick={() => setDialog(null)}
              />
              <Button
                type="submit"
                variant="primary"
                size="md"
                stretch="auto"
                label={t(`page_folders.${dialog?.action ?? "create"}`)}
                loading={isSubmitting}
                disabled={isSubmitting || (dialog?.action !== "delete" && !name.trim())}
              />
            </DialogActions>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
});
