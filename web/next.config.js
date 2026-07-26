/** @type {import('next').NextConfig} */
const nextConfig = {
  // 保持简单：不使用 standalone 输出，Docker runner 直接 next start。
  // 说明：本文件必须是 .js（而非 .ts）——生产 runner 镜像不含 typescript，
  // next start 遇到 next.config.ts 会尝试运行时在线安装 typescript。
  reactStrictMode: true,
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
};

module.exports = nextConfig;
