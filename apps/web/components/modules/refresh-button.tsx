/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { runInAction } from "mobx";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { DataRefreshButton } from "@/components/common/data-refresh-button";
import { useModule } from "@/hooks/store/use-module";
import { ModuleService } from "@/services/module.service";

const service = new ModuleService();

export const ModuleRefreshButton = observer(function ModuleRefreshButton() {
  const { workspaceSlug, projectId } = useParams();
  const { moduleMap, fetchedMap, loader } = useModule();

  const refresh = async () => {
    if (!workspaceSlug || !projectId) throw new Error("Missing project");
    const project = projectId.toString();
    const modules = await service.getModules(workspaceSlug.toString(), project);
    runInAction(() => {
      const ids = new Set(modules.map((module) => module.id));
      for (const module of Object.values(moduleMap)) {
        if (module.project_id === project && !module.archived_at && !ids.has(module.id)) {
          delete moduleMap[module.id];
        }
      }
      for (const module of modules) moduleMap[module.id] = { ...moduleMap[module.id], ...module };
      fetchedMap[project] = true;
    });
  };

  return (
    <DataRefreshButton
      key={`${workspaceSlug}:${projectId}`}
      onRefresh={refresh}
      disabled={!workspaceSlug || !projectId || loader}
    />
  );
});
