# Third-party notices

Original project code is MIT licensed (LICENSE). This is not an official Even Realities or Nous Research product. Trademarks remain with their respective owners.

## Distributed companion runtime

`@evenrealities/even_hub_sdk` 0.0.16 is bundled in the companion. Its actual npm package LICENSE (not merely registry metadata) contains the following notice, reproduced verbatim:

> MIT License
>
> Copyright (c) 2025 Yangshun Tay
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

Vite 7.3.7 generates the companion's build/preload helper. Its core license is MIT, Copyright (c) 2019-present, VoidZero Inc. and Vite contributors, under the same permission and warranty text above. The exact SDK license and complete Vite distribution license notices are also included in `companion/public/`, copied into built web and Even packages.

## Runtime/development dependencies

Hermes Agent v0.22.5 is installed separately under its MIT license; its source/runtime is not bundled here. aiohttp is a separately installed runtime dependency with license expression `Apache-2.0 AND MIT` (verified in the tested 3.14.5 distribution). Node/npm, TypeScript, Vitest, Playwright, Even Hub CLI and their transitive dependencies are development tools, installed from the committed npm lockfile; node_modules, browsers and upstream Hermes are not release assets. Consult each installed package's LICENSE for its terms. Release artifacts include no third-party browser binary.

No OcuClaw implementation was reused. A data-table NOTICE does not establish a software redistribution license. Platform enrollment, terms and marketplace permission are separate from this repository's source license.
