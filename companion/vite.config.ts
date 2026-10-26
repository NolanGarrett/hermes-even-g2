import {defineConfig} from 'vitest/config';
export default defineConfig({base:'./',build:{sourcemap:false},server:{host:'127.0.0.1'},
  test:{include:['tests/**/*.test.ts']}});
