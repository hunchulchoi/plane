import { describe, expect, it } from "vitest";
import { API_BASE_URL } from "@plane/constants";
import { getEditorAssetDownloadSrc, getEditorAssetSrc } from "@plane/utils";

const origin = API_BASE_URL;
const workspaceSlug = "zodiac";
const projectId = "6957a0a0-2cc2-41c0-953d-6f9605ca85e2";
const assetId = "55d2afb9-f1b5-4c26-ac9b-4eb6879b54bc";
const projectPath = `/api/assets/v2/workspaces/${workspaceSlug}/projects/${projectId}/`;
const workspacePath = `/api/assets/v2/workspaces/${workspaceSlug}/`;

describe("editor asset sources", () => {
  it.each([projectId, undefined])("resolves bare IDs with project scope %s", (scope) => {
    const path = scope ? projectPath : workspacePath;
    const args = { assetId, projectId: scope, workspaceSlug };
    expect(getEditorAssetSrc(args)).toBe(`${origin}${path}${assetId}/`);
    expect(getEditorAssetDownloadSrc(args)).toBe(`${origin}${path}download/${assetId}/`);
  });

  it.each([projectPath, workspacePath])("does not prefix a stored API path again: %s", (path) => {
    const args = { assetId: `${path}${assetId}/`, projectId: "other-project", workspaceSlug: "other-workspace" };
    expect(getEditorAssetSrc(args)).toBe(`${origin}${path}${assetId}/`);
    expect(getEditorAssetDownloadSrc(args)).toBe(`${origin}${path}download/${assetId}/`);
  });

  it("preserves queries and existing download paths", () => {
    const args = { assetId: `${projectPath}${assetId}?version=2`, projectId, workspaceSlug };
    const download = `${projectPath}download/${assetId}/?version=2`;
    expect(getEditorAssetDownloadSrc(args)).toBe(`${origin}${download}`);
    expect(getEditorAssetDownloadSrc({ ...args, assetId: download })).toBe(`${origin}${download}`);
  });

  it.each(["https://example.com/image.png", "/uploads/image.png"])("preserves image URLs: %s", (src) => {
    const args = { assetId: src, projectId, workspaceSlug };
    const expected = src.startsWith("/") ? `${origin}${src}` : src;
    expect(getEditorAssetSrc(args)).toBe(expected);
    expect(getEditorAssetDownloadSrc(args)).toBe(expected);
  });

  it("does not generate an asset endpoint for an empty source", () => {
    const args = { assetId: "", projectId, workspaceSlug };
    expect(getEditorAssetSrc(args)).toBeUndefined();
    expect(getEditorAssetDownloadSrc(args)).toBeUndefined();
  });
});
