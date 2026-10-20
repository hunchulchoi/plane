/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Folder } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Select } from "@plane/blocks/select";
import { setToast } from "@plane/blocks/toast";
import { usePageFolders } from "@/hooks/pages/use-page-folders";
import { EPageStoreType, usePageStore } from "@/hooks/store";
import type { TPageInstance } from "@/store/pages/base-page";

export const PageFolderSelect = observer(function PageFolderSelect({ page }: { page: TPageInstance }) {
  const { t } = useTranslation();
  const { folders, error: loadError, isLoading } = usePageFolders();
  const { movePageToFolder } = usePageStore(EPageStoreType.PROJECT);
  const [isMoving, setIsMoving] = useState(false);
  const options = [{ id: "", name: t("page_folders.no_folder") }, ...folders];
  const selected = options.find((folder) => folder.id === page.folder) ?? options[0];

  if (!page.canCurrentUserEditPage || page.is_locked || page.archived_at) return null;

  const move = async (folderId: string) => {
    if (!page.id || isMoving) return;
    setIsMoving(true);
    try {
      await movePageToFolder(page.id, folderId || null);
    } catch (error) {
      console.error("Unable to move page to folder", error);
      setToast({ type: "error", title: t("page_folders.error") });
    } finally {
      setIsMoving(false);
    }
  };

  return (
    <Select<{ id: string; name: string }>
      getValues={() => options}
      value={selected}
      onChange={(value) => {
        void move(value);
      }}
      getOptionValue={(folder) => folder.id}
      getOptionLabel={(folder) => folder.name}
      pinSelected={false}
      disabled={isMoving || isLoading || !!loadError}
    >
      <Select.Trigger variant="select-ghost-md" aria-label={t("page_folders.move")}>
        <Folder className="size-4 shrink-0" />
        <span className="max-w-32 truncate">{selected.name}</span>
      </Select.Trigger>
    </Select>
  );
});
