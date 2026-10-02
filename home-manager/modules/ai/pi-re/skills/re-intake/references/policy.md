# Engagement and capability policy

Read this before any workflow. The [operating contract](../../../contract.md#open-box-autonomy)
is authoritative for open-box autonomy, default capture and scope boundaries.
These guides teach wrappers and direct APIs; use actual installed interfaces and
report measured coverage.

## Authorization record

Record engagement/run ID and authorizer, allowed artifacts and target origins,
accounts, selected emulator/serial, package/build, and expiry/revocation terms.
Record which action classes the request covers: static inspection, sample
execution, instrumentation, navigation, fill/submit, capture, modification, replay,
scanning, helper/app installation, permission/trust changes, reset and deployment.
Apply the contract's routine-work scope rather than seeking each command's
approval. Give live work finite duration, rate, concurrency, request/storage
ceilings and stop conditions. A UI action may send network traffic.

Escalate a material action/target/account/device expansion, destructive reset,
provisioning outside the owned lab, credential/data-release change, expired
authorization or exhausted budget. In default capture mode, a previously unseen
hostname is expected evidence, not itself a scope expansion. Additional active
requests to third parties, cloud/OAST destinations or redirected replay targets
still need authorization. Stop on out-of-scope active actions, evidence leakage,
identity drift, unowned-resource collision or incompatible versions. Report the
blocked branch; continue independent authorized work if safe.

## Capability truth

Use `pi-re doctor` or `pi-re doctor --json` once at intake and after environment
changes. It is read-only: no implicit installation, scan, device connection,
repair, or credential refresh. Record actual output, not a fabricated schema.
Read installed help if report fields/options vary. A missing command is a blocked
interface, not permission to bootstrap the environment.

Availability, compatibility, qualification and enablement are separate facts.
Apply the [contract's capability interpretation](../../../contract.md#interfaces):
record qualification as coverage, not authorization. Verify installed versions,
help and required bindings/assets. Missing or incompatible functionality blocks
that operation; a compatible untested path gets a bounded experiment and explicit
partial result. A passing path does not certify unrelated combinations. Never
use an error hint as permission to download a tool, update a runtime or change scope.

Record actual doctor labels, including installed-unqualified where reported,
without overriding them from these guides. Recorded live coverage is summarized
in the [README](../../../README.md#verification-and-readiness); broader packs and
negative/adversarial coverage remain incomplete.

Implemented interfaces include `pi-re device` and `pi-re frida`, with owned-lab
selection/root checks and bundled attach instrumentation. Their status/help side
effects differ: only doctor and Android status promise no live probes; device
help/version are offline, while Frida status contacts/verifies the selected guest.
Read the runtime/UI guides before invoking them. Owned-lab setup within the
request covers bundled helper deployment on first snapshot; record helper/IME/
mapping changes rather than assuming pure observation.

No custom `pi-re flow` or native query/export script is promised; write bounded
task code or use installed direct APIs when appropriate. Wrapper allowlists do
not restrict ordinary Bash/files to those commands. Optional MCP, absent scanners,
GUI bridges, alternate UI stacks and remote/cloud device packs remain unfinished;
check actual availability instead of treating a guide as an implementation.
Root-only Flash delegation is enabled as specified in the
[contract](../../../contract.md#interfaces); child jobs inherit no broader scope.

## Host and credentials

Host/yolo is the chosen mode. It gives no whole-process sandbox or VM guarantee.
An emulator contains Android state, not every host analysis process. Execute an
unknown sample only inside a separately approved whole-process lab boundary.
Static parsers also process hostile data; use finite resource limits and avoid
running extracted code or build hooks. If risk needs isolation absent here, block.

The RE profile is separate and writable, with copied provider/login configuration.
Keep ordinary coding settings/resources untouched. Never inspect credentials to
prove separation; use path/ownership facts from approved metadata. Copying login
state is not redaction and unrestricted children may read it. Confirm provider
and approved-data policy before exposing target evidence to a model.

## Ownership and recovery

For each device/session/page/context/capture/project/process, record run ID,
endpoint or serial, artifact root, owner and readiness/identity evidence.
Serialize device mutations and Ghidra project writers. Reject foreign/uncertain
claims. PID alone is insufficient: verify start identity and ownership before stop.
Set deadlines before launch, retain private diagnostics, cancel cooperatively,
and escalate only against verified owned resources. After interruption, inspect
owned state before retry; an action may have completed despite a lost response.
Close only owned pages/sessions; preserve evidence before deleting working copies.
Global daemon stops, broad `pkill`, personal-browser attachment and unrelated
project cleanup are not recovery procedures.
