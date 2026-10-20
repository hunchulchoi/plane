/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "@plane/i18n";
// types
import type { TPageNavigationTabs } from "@plane/types";
// components
import { ListLayout } from "@/components/core/list";
// plane web hooks
import type { EPageStoreType } from "@/hooks/store";
import { usePageStore } from "@/hooks/store";
// local imports
import { PageListBlock } from "./block";

type TPagesListRoot = {
  pageType: TPageNavigationTabs;
  storeType: EPageStoreType;
};

export const PagesListRoot = observer(function PagesListRoot(props: TPagesListRoot) {
  const { pageType, storeType } = props;
  // store hooks
  const { getCurrentProjectFilteredPageIdsByTab, getPageById } = usePageStore(storeType);
  const { t } = useTranslation();
  const folderId = useSearchParams().get("folder");
  // derived values
  const filteredPageIds = getCurrentProjectFilteredPageIdsByTab(pageType);
  const visiblePageIds = folderId
    ? filteredPageIds?.filter((id) => getPageById(id)?.folder === folderId)
    : filteredPageIds;

  if (!visiblePageIds) return <></>;
  if (folderId && visiblePageIds.length === 0)
    return <p className="p-6 text-13 text-tertiary">{t("page_folders.empty")}</p>;
  return (
    <ListLayout>
      {visiblePageIds.map((pageId) => (
        <PageListBlock key={pageId} pageId={pageId} storeType={storeType} />
      ))}
    </ListLayout>
  );
});
