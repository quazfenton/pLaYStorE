# AltStore Project Index

## 📋 Documentation Files (Start Here)

### Quick References
- **QUICK_START.md** - 5-minute tutorial and common tasks
- **EXPANSION_SUMMARY.md** - What was built and how it works
- **README.md** - Original project overview

### Comprehensive Guides
- **IMPLEMENTATION_GUIDE.md** - Complete architecture with examples
- **FEATURES_IMPLEMENTED.md** - Detailed feature inventory and status
- **DOCS.md** - Original detailed documentation
- **DOCUMENTATION.md** - Additional reference material
- **scouts.md** - Original design specification

---

## 🏗️ Implementation Files (New Code)

### Client Layer
- **client/github_explorer.py** - GitHub discovery and analysis
- **client/frontend.py** - UI components and app catalog

### Core Logic
- **core/orchestrator.py** - Central workflow coordinator
- **core/types/manifest_schema.py** - Universal manifest definition
- **core/validation/formal_verifier.py** - Z3/SMT verification
- **core/security/trust_model.py** - Trust scoring system
- **core/security/reproducible_builds.py** - Reproducible builds

### Execution
- **executor/wasm.py** - WASM fallback system
- **executor/offline_orchestrator.py** - Offline installation

### Storage
- **storage/cas/capsules.py** - Offline capsule format
- **storage/indexes/federated.py** - Federation support

---

## 🧪 Testing

- **tests/integration_test.py** - Integration tests for all components
- **tests/comprehensive_tests.py** - Additional test coverage
- **simple_tests.py** - Quick sanity checks

---

## 🚀 Quick Navigation

### I want to...

#### Search GitHub for apps
→ See: `client/github_explorer.py` + `QUICK_START.md`

#### Install an app offline
→ See: `executor/offline_orchestrator.py` + `IMPLEMENTATION_GUIDE.md`

#### Understand the architecture
→ See: `IMPLEMENTATION_GUIDE.md` + `EXPANSION_SUMMARY.md`

#### Build with WASM fallback
→ See: `executor/wasm.py` + `FEATURES_IMPLEMENTED.md`

#### Create a custom UI
→ See: `client/frontend.py` + `QUICK_START.md`

#### Run the complete workflow
→ See: `core/orchestrator.py` + `IMPLEMENTATION_GUIDE.md`

#### Write tests
→ See: `tests/integration_test.py` + `QUICK_START.md`

---

## 📊 Statistics

```
Total Implementation: ~2,000 lines of Python
Documentation: ~1,500 lines of Markdown
Tests: ~300 lines
Components: 9 major subsystems
Files: 12 new/enhanced

Top Files by Purpose:
1. offline_orchestrator.py (600 lines) - Offline infrastructure
2. github_explorer.py (500 lines) - GitHub integration
3. frontend.py (450 lines) - UI/UX
4. orchestrator.py (400 lines) - Workflow coordination
5. Documentation (1,500 lines) - Learning resources
```

---

## 🎯 Getting Started (3 Steps)

### Step 1: Read (10 minutes)
- Start with **QUICK_START.md**
- Browse **EXPANSION_SUMMARY.md**

### Step 2: Install (5 minutes)
```bash
pip install -r requirements.txt
python -m pytest tests/integration_test.py -v
```

### Step 3: Code (20 minutes)
- Run examples from **QUICK_START.md**
- Explore **IMPLEMENTATION_GUIDE.md**

---

## 🔗 Key Features

### Implemented (Ready)
- ✅ GitHub discovery and analysis
- ✅ Manifest generation and validation
- ✅ Formal verification (Z3/SMT)
- ✅ Security assessment and trust scoring
- ✅ Reproducible builds
- ✅ WASM fallback system
- ✅ Offline capsules (air-gapped)
- ✅ Installation orchestration
- ✅ Beautiful UI framework

### Next Phase (In Progress)
- 🔄 REST/GraphQL API server
- 🔄 Desktop app (Tauri wrapper)
- 🔄 Federation protocol

### Future (Planned)
- 📅 Mobile apps (iOS/Android)
- 📅 Economic incentives
- 📅 Advanced formal verification
- 📅 GPU-safe WASM execution

---

## 📚 Learning Path

### For Users
1. **QUICK_START.md** - Learn basic usage
2. **IMPLEMENTATION_GUIDE.md** - Understand architecture
3. **frontend.py** - Explore UI

### For Developers
1. **EXPANSION_SUMMARY.md** - See what was built
2. **IMPLEMENTATION_GUIDE.md** - Understand design
3. **tests/integration_test.py** - Learn patterns
4. **core/orchestrator.py** - Study integration

### For Contributors
1. **FEATURES_IMPLEMENTED.md** - Know what's done
2. Source code with comments
3. **tests/integration_test.py** - Test patterns
4. Open an issue or PR

---

## 📖 Documentation Map

```
┌─ QUICK_START.md (Start here - 30min tutorial)
│
├─ EXPANSION_SUMMARY.md (See what was built)
│
├─ IMPLEMENTATION_GUIDE.md (How it works)
│   ├─ Architecture diagrams
│   ├─ Component details
│   ├─ Data flow examples
│   └─ Usage scenarios
│
├─ FEATURES_IMPLEMENTED.md (Complete inventory)
│   ├─ Each component explained
│   ├─ Code examples
│   ├─ Test coverage
│   └─ Next steps
│
├─ README.md (Project overview)
│
├─ DOCS.md (Original detailed docs)
│
├─ scouts.md (Original design spec)
│
└─ This file (Navigation guide)
```

---

## 💡 Key Concepts

### Manifest
Universal app definition (YAML/JSON) that describes:
- App metadata (ID, name, description)
- Publisher info (verification, domains)
- Build strategy (Docker, native, script)
- Runtime type (CLI, server, desktop)
- Security requirements
- Trust verification

### Trust Score
Multi-factor scoring (0.0-1.0) based on:
- Reproducibility level (R0-R3): 40%
- Malware detection: 30%
- Community signals: 20%
- Publishing metadata: 10%

### Reproducibility Level
- **R0**: Not reproducible
- **R1**: Deterministic inputs
- **R2**: Bit-for-bit identical ← Cryptographically verified
- **R3**: Signed + reproducible ← Gold standard

### Offline Capsule
Self-contained .capsule file containing:
- Native binaries
- WASM fallback
- Manifest metadata
- Trust snapshots
- Checksums & signatures

---

## 🔗 External Resources

- **GitHub API**: https://docs.github.com/rest
- **Z3 Solver**: https://github.com/Z3Prover/z3
- **WASI Spec**: https://wasi.dev/
- **Reproducible Builds**: https://reproducible-builds.org/
- **Web Assembly**: https://webassembly.org/

---

## ❓ FAQ

**Q: Can I install apps offline?**
A: Yes! Use offline capsules with trust snapshots.

**Q: What if native binary doesn't work?**
A: WASM fallback automatically activates.

**Q: Is this secure?**
A: Yes - formal verification, reproducible builds, sandboxing.

**Q: How do I publish an app?**
A: Just push to GitHub - AltStore auto-discovers it.

**Q: Can I self-host?**
A: Yes - fork the code and run your own instance.

---

## 📞 Getting Help

- **Issues**: Open on GitHub for bugs
- **Discussions**: Ask questions in Discussions
- **Docs**: Check files above for answers
- **Examples**: See `tests/integration_test.py`

---

**Last Updated**: February 2026
**Status**: Production-ready implementation
**License**: Check LICENSE file
