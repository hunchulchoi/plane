/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TForgejoRepository = {
  id: string;
  project_id: string;
  project_name: string;
  repository_url: string;
  webhook_url: string;
  last_received_at: string | null;
  secret?: string;
};

export class ForgejoService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async list(slug: string): Promise<TForgejoRepository[]> {
    const response = await this.get(`/api/workspaces/${slug}/forgejo-repositories/`);
    return response.data;
  }

  async connect(slug: string, projectId: string, repositoryUrl: string): Promise<TForgejoRepository> {
    const response = await this.post(`/api/workspaces/${slug}/forgejo-repositories/`, {
      project_id: projectId,
      repository_url: repositoryUrl,
    });
    return response.data;
  }

  async disconnect(slug: string, id: string): Promise<void> {
    await this.delete(`/api/workspaces/${slug}/forgejo-repositories/${id}/`);
  }
}
