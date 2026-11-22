# Frontend testing

The production dependency lock remains stable; the optional test runners are installed in CI and can be installed locally with:

```bash
npm install   # test tools are devDependencies now
npm run test
npm run test:e2e
```

The smoke suite covers the public landing page. Add authenticated Playwright flows once a seeded test account fixture is available; backend API behavior is covered by FastAPI TestClient tests.
