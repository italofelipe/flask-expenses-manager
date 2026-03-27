# Changelog

## [1.7.0](https://github.com/italofelipe/auraxis-api/compare/v1.6.0...v1.7.0) (2026-03-27)


### Features

* **gov:** add pr traceability checks ([#722](https://github.com/italofelipe/auraxis-api/issues/722)) ([cb7896e](https://github.com/italofelipe/auraxis-api/commit/cb7896e9bb492fa8a759426eae34893f9ec372c5))
* **j2:** complete bank statement import flow ([#720](https://github.com/italofelipe/auraxis-api/issues/720)) ([6ffaab3](https://github.com/italofelipe/auraxis-api/commit/6ffaab3fcb81b21db0c7663536b38b03a4110aff))
* **obs:** enrich lightweight request correlation ([#726](https://github.com/italofelipe/auraxis-api/issues/726)) ([458c595](https://github.com/italofelipe/auraxis-api/commit/458c59582b784e71aa1ef0427d7607b306708ed5))
* **perf:** add latency budget governance gate ([#724](https://github.com/italofelipe/auraxis-api/issues/724)) ([21ad839](https://github.com/italofelipe/auraxis-api/commit/21ad839cf937334e0dc5a0ad58cbf391981aba3f))
* **user:** add explicit bootstrap endpoint ([#738](https://github.com/italofelipe/auraxis-api/issues/738)) ([5fa4b39](https://github.com/italofelipe/auraxis-api/commit/5fa4b39262d75d2cd6f79822883d5a12a9911dd5))
* **user:** publish canonical me contract ([#737](https://github.com/italofelipe/auraxis-api/issues/737)) ([2fc0c21](https://github.com/italofelipe/auraxis-api/commit/2fc0c2133e9cbdf3f5098e9553d8885da84dcbe9))

## [1.6.0](https://github.com/italofelipe/auraxis-api/compare/v1.5.0...v1.6.0) (2026-03-26)


### Features

* **j2:** add bank import transaction foundation ([#716](https://github.com/italofelipe/auraxis-api/issues/716)) ([7106379](https://github.com/italofelipe/auraxis-api/commit/71063799d7c04a80d76b7f1f2e76c63418d3cd95))
* **j2:** add ofx and nubank parsers ([#717](https://github.com/italofelipe/auraxis-api/issues/717)) ([7c28d08](https://github.com/italofelipe/auraxis-api/commit/7c28d087202468da2f83c9bbc601ca865e6b0849))


### Bug Fixes

* **ops:** run recurrence job via ssm ([#714](https://github.com/italofelipe/auraxis-api/issues/714)) ([ee26ffe](https://github.com/italofelipe/auraxis-api/commit/ee26ffe2ab47f1405922bd8f9ddee64e09d923f8))

## [1.5.0](https://github.com/italofelipe/auraxis-api/compare/v1.4.0...v1.5.0) (2026-03-26)


### Features

* **api:** unify rest errors and add latency baseline ([#700](https://github.com/italofelipe/auraxis-api/issues/700)) ([f3c807d](https://github.com/italofelipe/auraxis-api/commit/f3c807d8ea21957ce984fac022bdf0d4f263e115))
* **observability:** add low-cost api ops baseline ([#698](https://github.com/italofelipe/auraxis-api/issues/698)) ([062a4af](https://github.com/italofelipe/auraxis-api/commit/062a4af2361cde185972d9542bb498a1d078601a))


### Bug Fixes

* **api:** bootstrap operational scripts from repo root ([#702](https://github.com/italofelipe/auraxis-api/issues/702)) ([15303e5](https://github.com/italofelipe/auraxis-api/commit/15303e531f756e1391e674b61e14920bcaa712a0))
* isolate internal runtime from http middleware ([#706](https://github.com/italofelipe/auraxis-api/issues/706)) ([dba5d4d](https://github.com/italofelipe/auraxis-api/commit/dba5d4d08dc98409898c0df170537d03af90fefa))

## [1.4.0](https://github.com/italofelipe/auraxis-api/compare/v1.3.0...v1.4.0) (2026-03-22)


### Features

* **postman:** audit remaining route parity gaps ([#684](https://github.com/italofelipe/auraxis-api/issues/684)) ([e35dbe6](https://github.com/italofelipe/auraxis-api/commit/e35dbe62f4c8e26eb76cc751bb89e8c79d1199c9))
* **postman:** expand canonical e2e parity coverage ([#682](https://github.com/italofelipe/auraxis-api/issues/682)) ([45d6dc2](https://github.com/italofelipe/auraxis-api/commit/45d6dc2802fad8a869c81e8ca25cf99c326b049c))
* **postman:** isolate privileged integration profile ([#683](https://github.com/italofelipe/auraxis-api/issues/683)) ([dfc6b5d](https://github.com/italofelipe/auraxis-api/commit/dfc6b5d062971ee1753793794f2f5514b31c8bee))
* **test:** add smoke and full postman profiles ([#669](https://github.com/italofelipe/auraxis-api/issues/669)) ([dd19e82](https://github.com/italofelipe/auraxis-api/commit/dd19e82dea39ff9a75ca84f8c19cd3576ad40ae4))


### Bug Fixes

* **auth:** harden webhook boundary and remove legacy jwt path ([#679](https://github.com/italofelipe/auraxis-api/issues/679)) ([774aab9](https://github.com/italofelipe/auraxis-api/commit/774aab991528a880610a9b4b4bd5f846b763417d))
* **ci:** add dedicated newman integration gate ([#681](https://github.com/italofelipe/auraxis-api/issues/681)) ([866cd48](https://github.com/italofelipe/auraxis-api/commit/866cd482cfd34c74ddb604107025006edf19ad76))
* **ops:** harden recurrence incidents and rate limit fallback ([#680](https://github.com/italofelipe/auraxis-api/issues/680)) ([784ab2c](https://github.com/italofelipe/auraxis-api/commit/784ab2cf88ac0ad1e8eec7673218845ec78108cf))
* **ops:** stabilize newman full runtime drift ([#686](https://github.com/italofelipe/auraxis-api/issues/686)) ([9441a52](https://github.com/italofelipe/auraxis-api/commit/9441a5215a9ea2bae6699c6f2c73808a54e12d0e))

## [1.3.0](https://github.com/italofelipe/auraxis-api/compare/v1.2.0...v1.3.0) (2026-03-22)


### Features

* **infra:** add alb edge mode for api runtime ([#658](https://github.com/italofelipe/auraxis-api/issues/658)) ([d0cb02d](https://github.com/italofelipe/auraxis-api/commit/d0cb02dd46598ad96ba89a243671ec6a832978e2))
* **ops:** automate dev host recovery baseline ([#664](https://github.com/italofelipe/auraxis-api/issues/664)) ([7663ee1](https://github.com/italofelipe/auraxis-api/commit/7663ee1ff27e607b7138271cf64164239d3cf197))
* **ops:** improve deploy and sonar diagnostics ([#665](https://github.com/italofelipe/auraxis-api/issues/665)) ([9588e47](https://github.com/italofelipe/auraxis-api/commit/9588e475ab86b9500b2db8763d9f3c7351e93e8c))
* **testing:** establish canonical postman e2e suite ([#668](https://github.com/italofelipe/auraxis-api/issues/668)) ([5aebfe2](https://github.com/italofelipe/auraxis-api/commit/5aebfe24000f04bbf0a8fb6eb014c330d1977834))


### Bug Fixes

* **deploy:** add dual edge mode for alb cutover ([#662](https://github.com/italofelipe/auraxis-api/issues/662)) ([f53d416](https://github.com/italofelipe/auraxis-api/commit/f53d416636e5cc1b39985e4fa92d753c86e7ec4a))

## [1.2.0](https://github.com/italofelipe/auraxis-api/compare/v1.1.0...v1.2.0) (2026-03-21)


### Features

* add installment vs cash simulation contract ([#647](https://github.com/italofelipe/auraxis-api/issues/647)) ([02019f5](https://github.com/italofelipe/auraxis-api/commit/02019f549f3ef86b36a60e62cd8adab935ed2ef9))


### Bug Fixes

* **ci:** let release please trigger release pr checks ([#643](https://github.com/italofelipe/auraxis-api/issues/643)) ([f05f809](https://github.com/italofelipe/auraxis-api/commit/f05f80978f5048f44d5f5d2d40d90934206fc25f))

## [1.1.0](https://github.com/italofelipe/auraxis-api/compare/v1.0.0...v1.1.0) (2026-03-19)


### Features

* **alerts:** J11-2 — alert dispatch matrix and scheduler endpoints ([#627](https://github.com/italofelipe/auraxis-api/issues/627)) ([f6e7ac0](https://github.com/italofelipe/auraxis-api/commit/f6e7ac02b0c6aaeefef25e0d630c3a3d0c8ebb52))
* **infra:** integrate Sentry SDK with Flask for error tracking and performance monitoring ([#625](https://github.com/italofelipe/auraxis-api/issues/625)) ([48a7b36](https://github.com/italofelipe/auraxis-api/commit/48a7b36a2f6c68d4cef212943f6d28a99ac217cb)), closes [#616](https://github.com/italofelipe/auraxis-api/issues/616)
* **infra:** smoke test automatizado pós-deploy via Newman (DoD [#617](https://github.com/italofelipe/auraxis-api/issues/617)) ([#632](https://github.com/italofelipe/auraxis-api/issues/632)) ([b22976b](https://github.com/italofelipe/auraxis-api/commit/b22976b2d11e35807c89641520022d143ff14056))
* **j12:** subscription state & entitlement enforcement ([#629](https://github.com/italofelipe/auraxis-api/issues/629)) ([c32b768](https://github.com/italofelipe/auraxis-api/commit/c32b76831205499a4e72cd6149af59872752356a))
* **j13:** shared entries, invitations and audit contract ([#630](https://github.com/italofelipe/auraxis-api/issues/630)) ([913a06a](https://github.com/italofelipe/auraxis-api/commit/913a06ac57607548a477dcb0697da36079ce31f3))
* **j14:** generic CSV ingestion and receivable/fiscal document endpoints ([#631](https://github.com/italofelipe/auraxis-api/issues/631)) ([1cedb62](https://github.com/italofelipe/auraxis-api/commit/1cedb6258f4e1fb510c177ea2be13fc4e250289e))
* **j7:** simulation persistence, goals PATCH and entitlement endpoints ([#628](https://github.com/italofelipe/auraxis-api/issues/628)) ([1334488](https://github.com/italofelipe/auraxis-api/commit/133448851f80c4d9e813b0b82820f8a07fec1c13))
* **j9:** billing provider adapter and subscription state endpoints ([#626](https://github.com/italofelipe/auraxis-api/issues/626)) ([aaa867c](https://github.com/italofelipe/auraxis-api/commit/aaa867c2e1c4125aee366d1c531090fde22068c8))
* **models+migrations:** complete J-task foundation — Entitlement model, migration, and unit tests ([#624](https://github.com/italofelipe/auraxis-api/issues/624)) ([1697757](https://github.com/italofelipe/auraxis-api/commit/16977575a0b811459c1774e2ef12034c4a5f7406))
* **user:** implement investor profile questionnaire ([#588](https://github.com/italofelipe/auraxis-api/issues/588)) ([130ddae](https://github.com/italofelipe/auraxis-api/commit/130ddaeb3520a9f76084aa4cddbda2ca6901b77d))
* **user:** implement salary increase simulation endpoint ([#603](https://github.com/italofelipe/auraxis-api/issues/603)) ([a48bfb2](https://github.com/italofelipe/auraxis-api/commit/a48bfb22cf3f431f466fdd26c6a0f9978a15de54))

## Changelog

All notable changes to this project will be documented in this file.

This file is the baseline for automated release management via Release Please.
Subsequent entries should be generated from release automation.
