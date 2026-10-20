/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useParams } from "next/navigation";
import useSWR from "swr";
import { ProjectPageService } from "@/services/page";

export const pageFolderService = new ProjectPageService();

export function usePageFolders() {
  const { workspaceSlug, projectId } = useParams();
  const slug = workspaceSlug?.toString() ?? "";
  const project = projectId?.toString() ?? "";
  const result = useSWR(slug && project ? ["PROJECT_PAGE_FOLDERS", slug, project] : null, () =>
    pageFolderService.fetchFolders(slug, project)
  );
  return { ...result, folders: result.data ?? [], workspaceSlug: slug, projectId: project };
}
