import { defineConfig } from 'tsup'

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'vercel-ai': 'wrappers/vercel-ai.ts',
    config: 'src/config.ts',
    cli: 'src/cli.ts',
    bin: 'src/bin.ts',
  },
  format: ['cjs', 'esm'],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  external: ['ai'],
})
