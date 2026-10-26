import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./browser',workers:1,use:{channel:'chromium',baseURL:'http://127.0.0.1:4173',viewport:{width:390,height:844}},
  webServer:{command:'npm run dev -- --port 4173',url:'http://127.0.0.1:4173',reuseExistingServer:false},
  reporter:'list'});
