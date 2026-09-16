<br /><br />

<p align="center">
<a href="https://plane.so">
  <img src="https://media.docs.plane.so/logo/plane_github_readme.png" alt="Plane Logo" width="400">
</a>
</p>
<p align="center"><b>Modern project management for all teams</b></p>

<p align="center">
    <a href="https://plane.so/"><b>Website</b></a> •
    <a href="https://forum.plane.so"><b>Forum</b></a> •
    <a href="https://x.com/planepowers"><b>X</b></a> •
    <a href="https://docs.plane.so/"><b>Documentation</b></a>
</p>

<p>
    <a href="https://app.plane.so/#gh-light-mode-only" target="_blank">
      <img
        src="https://media.docs.plane.so/GitHub-readme/github-top.webp"
        alt="Plane Screens"
        width="100%"
      />
    </a>
</p>

Meet [Plane](https://plane.so/), an open-source project management tool to track issues, run ~sprints~ cycles, and manage product roadmaps without the chaos of managing the tool itself. 🧘‍♀️

> Plane is evolving every day. Your suggestions, ideas, and reported bugs help us immensely. Do not hesitate to join in the conversation on [Forum](https://forum.plane.so) or raise a GitHub issue. We read everything and respond to most.

## 🚀 Installation

Getting started with Plane is simple. Choose the setup that works best for you:

- **Plane Cloud**
  Sign up for a free account on [Plane Cloud](https://app.plane.so)—it's the fastest way to get up and running without worrying about infrastructure.

- **Self-host Plane**
  Prefer full control over your data and infrastructure? Install and run Plane on your own servers. Follow our detailed [deployment guides](https://developers.plane.so/self-hosting/overview) to get started.

| Installation methods | Docs link                                                                                                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Docker               | [![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://developers.plane.so/self-hosting/methods/docker-compose)         |
| Kubernetes           | [![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)](https://developers.plane.so/self-hosting/methods/kubernetes) |
| Managed hosting      | [<img alt="Deploy with Zenith" src="https://cdn.zenith.hosting/buttons/deploy-with-zenith.svg" height="40">](https://zenith.hosting/host/plane) |

`Instance admins` can configure instance settings with [God mode](https://developers.plane.so/self-hosting/govern/instance-admin).

## 🌟 Features

- **Work Items**
  Efficiently create and manage tasks with a robust rich text editor that supports file uploads. Enhance organization and tracking by adding sub-properties and referencing related issues.

- **Cycles**
  Maintain your team’s momentum with Cycles. Track progress effortlessly using burn-down charts and other insightful tools.

- **Modules**
  Simplify complex projects by dividing them into smaller, manageable modules.

- **Views**
  Customize your workflow by creating filters to display only the most relevant issues. Save and share these views with ease.

- **Pages**
  Capture and organize ideas using Plane Pages, complete with AI capabilities and a rich text editor. Format text, insert images, add hyperlinks, or convert your notes into actionable items.

- **Analytics**
  Access real-time insights across all your Plane data. Visualize trends, remove blockers, and keep your projects moving forward.

## 🛠️ Local development

See [CONTRIBUTING](./CONTRIBUTING.md)

## ⚙️ Built with

[![React Router](https://img.shields.io/badge/-React%20Router-CA4245?logo=react-router&style=for-the-badge&logoColor=white)](https://reactrouter.com/)
[![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=green)](https://www.djangoproject.com/)
[![Node JS](https://img.shields.io/badge/node.js-339933?style=for-the-badge&logo=Node.js&logoColor=white)](https://nodejs.org/en)

## 📸 Screenshots

  <p>
    <a href="https://plane.so" target="_blank">
      <img
        src="https://media.docs.plane.so/GitHub-readme/github-work-items.webp"
        alt="Plane Views"
        width="100%"
      />
    </a>
  </p>
  <p>
    <a href="https://plane.so" target="_blank">
      <img
        src="https://media.docs.plane.so/GitHub-readme/github-cycles.webp"
        width="100%"
      />
    </a>
  </p>
  <p>
    <a href="https://plane.so" target="_blank">
      <img
        src="https://media.docs.plane.so/GitHub-readme/github-modules.webp"
        alt="Plane Cycles and Modules"
        width="100%"
      />
    </a>
  </p>
  <p>
    <a href="https://plane.so" target="_blank">
      <img
        src="https://media.docs.plane.so/GitHub-readme/github-views.webp"
        alt="Plane Analytics"
        width="100%"
      />
    </a>
  </p>
   <p>
    <a href="https://plane.so" target="_blank">
      <img
        src="https://media.docs.plane.so/GitHub-readme/github-analytics.webp"
        alt="Plane Pages"
        width="100%"
      />
    </a>
  </p>
</p>

## Source-built deployment

This branch builds Plane from the checked-out source and serves it at
`https://plane.devfor.link`. It reuses the host's shared PostgreSQL and MinIO
with Plane-specific credentials; Valkey and RabbitMQ remain isolated in the
Plane Compose project.

Prerequisites are Docker Compose v2, running containers named `postgres` and
`minio`, their administrator environment files in the sibling configuration
tree, and the existing Traefik deployment. SMTP and optional OAuth providers
are intentionally unconfigured.

```bash
./scripts/deploy.sh
./scripts/rebuild.sh web
./scripts/rebuild.sh api worker beat-worker
./scripts/verify.sh
```

### Project attachment upload flow

Project attachments, including PDFs and other supported documents, use a
three-step presigned upload. Create the asset by posting metadata to the
collection URL (without an asset UUID), submit every returned
`upload_data.fields` value plus the file as multipart form data to
`upload_data.url`, and only then mark the asset uploaded with PATCH:

```text
POST  /api/assets/v2/workspaces/{workspace}/projects/{project}/
POST  {upload_data.url}  (multipart fields + file; no Plane API headers)
PATCH /api/assets/v2/workspaces/{workspace}/projects/{project}/{asset_id}/
```

Do not POST to the final asset-detail URL. The local Plane CLI automates this
flow with `plane assets upload` and `plane pages attach`.

The shared Traefik obtains the `plane.devfor.link` certificate through a
Cloudflare DNS-01 challenge. Store a zone-scoped `CF_DNS_API_TOKEN` in the
Traefik sibling directory's mode-`0600` `.env`, then apply the idempotent
configuration with `./scripts/configure-traefik-acme.sh` before recreating
Traefik. The ACME account and certificates persist in
`../../traefik/letsencrypt/acme.json`.

Generated credentials live only in ignored, mode-`0600` `.env`. Roll back by
checking out a known custom-branch commit and rebuilding affected services;
the provisioning scripts never delete shared resources.

Review release notes and migrations before incorporating a stable upstream
release into a new customization branch:

```bash
git fetch upstream --tags
git switch -c custom/vNEXT vNEXT
git merge custom/v1.4.2
git push -u origin custom/vNEXT
```

Plane is licensed under AGPL-3.0. Preserve its license and corresponding-source
obligations when offering a modified instance over a network.

## 📝 Documentation

Explore Plane's [product documentation](https://docs.plane.so/) and [developer documentation](https://developers.plane.so/) to learn about features, setup, and usage.

## ❤️ Community

Join the Plane community on [GitHub Discussions](https://github.com/orgs/makeplane/discussions) and our [Forum](https://forum.plane.so). We follow a [Code of conduct](https://github.com/makeplane/plane/blob/master/CODE_OF_CONDUCT.md) in all our community channels.

Feel free to ask questions, report bugs, participate in discussions, share ideas, request features, or showcase your projects. We’d love to hear from you!

## 🛡️ Security

If you discover a security vulnerability in Plane, please report it responsibly instead of opening a public issue. We take all legitimate reports seriously and will investigate them promptly. See [Security policy](https://github.com/makeplane/plane/blob/master/SECURITY.md) for more info.

To disclose any security issues, please email us at security@plane.so.

## 🤝 Contributing

There are many ways you can contribute to Plane:

- Report [bugs](https://github.com/makeplane/plane/issues/new?assignees=srinivaspendem%2Cpushya22&labels=%F0%9F%90%9Bbug&projects=&template=--bug-report.yaml&title=%5Bbug%5D%3A+) or submit [feature requests](https://github.com/makeplane/plane/issues/new?assignees=srinivaspendem%2Cpushya22&labels=%E2%9C%A8feature&projects=&template=--feature-request.yaml&title=%5Bfeature%5D%3A+).
- Review the [documentation](https://docs.plane.so/) and submit [pull requests](https://github.com/makeplane/docs) to improve it—whether it's fixing typos or adding new content.
- Talk or write about Plane or any other ecosystem integration and [let us know](https://forum.plane.so)!
- Show your support by upvoting [popular feature requests](https://github.com/makeplane/plane/issues).

Please read [CONTRIBUTING.md](https://github.com/makeplane/plane/blob/master/CONTRIBUTING.md) for details on the process for submitting pull requests to us.

### Repo activity

![Plane Repo Activity](https://repobeats.axiom.co/api/embed/2523c6ed2f77c082b7908c33e2ab208981d76c39.svg "Repobeats analytics image")

### We couldn't have done this without you.

<a href="https://github.com/makeplane/plane/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=makeplane/plane" />
</a>

## License

This project is licensed under the [GNU Affero General Public License v3.0](https://github.com/makeplane/plane/blob/master/LICENSE.txt).
