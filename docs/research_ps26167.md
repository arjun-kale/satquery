# Evidence base: SIH 2026 PS 26167 — SatQuery AI

Research date: 19 September 2026. Team: SPT02 “Team Invincible”.

Evidence labels: **[UNVERIFIED]** means no reliable source was located in this review. **[INFERRED]** means a conclusion follows from cited material but is not directly stated by it.

## Ground truth

The official SIH page was not machine-accessible in this environment. The following was retrieved from a community mirror which preserves an SIH scrape dated 21 August 2026 and identifies `sih.gov.in/sih2026PS` as source: [PS record](https://github.com/aditya-kr86/sih2026/blob/main/ps_2026/SIH26167.md).

* Exact title: “SatQuery AI - An Interactive Vision-Language Assistant for Multimodal Remote Sensing Image Analysis through Text Queries”
* Sponsoring organisation: “Indian Space Research Organisation(ISRO)”
* Department: “Department of Space / Indian Space Research Organisation”
* Category: “Software”
* Theme: “Space Technology”
* Submitted ideas: `0/500` in the 21 August scrape; **[UNVERIFIED]** as the live 19 September count.

The statement names “BigEarthNet.txt,” “VRSBench,” “RSVQA,” “CDVQA,” “GeoTIFF or TIFF,” “co-registered optical–SAR pairs,” “bi-temporal pairs,” “agentic controller,” “visual evidence, confidence information, execution summaries, and downloadable reports.” It says the ISRO/SAC set contains “pre-georeferenced and co-registered Cartosat-2S optical and RISAT SAR image pairs.” A generic LLM/VLM without remote-sensing adaptation does not meet the requirement.

## Q1. Competitive field

The archive records `0/500` on 21 August, but this cannot establish the live count or median across ISRO statements. Both are **[UNVERIFIED]** pending a manual SIH check.

Public self-reports show active competition: a LinkedIn-indexed post says Team Debuggers Den addressed PS 26167 at JECRC HackQuest 9.0; another says Team Atulya was Top 50 in its internal selection and used Qwen2.5-VL, bi-temporal change analysis and optical–SAR analysis. A public repository, [`awdtyo/SatQueryAI-SIH26`](https://github.com/awdtyo/SatQueryAI-SIH26), advertises BigEarthNet/VRSBench/RSVQA training. These are not independent evaluations. Sources: [Debuggers Den result](https://in.linkedin.com/in/ananyabiju), [Atulya result](https://in.linkedin.com/in/md-asad-raza-ba2b97310).

Decision impact: active architectural competition is established; a numerical differentiation claim is not.

## Q2. Incumbent workflow

No public NRSC tender found in this review proves current ERDAS IMAGINE, ArcGIS or ENVI seat counts, values, or analyst turnaround times. Do not claim any numeric time saving.

The documented public workflow is:

1. Discover imagery/products in NRSC/Bhoonidhi or thematic layers in Bhuvan. Bhoonidhi offers open 5 m-and-coarser data to registered users; Bhuvan exposes thematic layers and services. [Bhoonidhi terms](https://bhoonidhi.nrsc.gov.in/bhoonidhi/htmls/TnC.html), [Bhuvan portal](https://bhuvan.nrsc.gov.in/bhuvan_links.php).
2. Choose data by AOI, date, sensor/product and resolution, then acquire it. NRSC says GSD >=5 m is open/free; finer data follows different government/NGE terms. [NRSC policy](https://www.nrsc.gov.in/nrscnew/pnp_order_policy.php).
3. Consume Bhuvan OGC WMS/WMTS in a GIS client. Its documented layers include LULC, water bodies, flood and glacial-lake layers; WMS endpoint is `https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms`. [Bhuvan WMS guide](https://bhuvan.nrsc.gov.in/wiki/index.php/How_to_use_WMS_services).
4. Co-register/harmonise dates and sensors, subset the AOI, manage clouds/radiometry, then create an index, classification or interpreted change layer. This processing chain is **[INFERRED]** from the PS’s mandatory paired-image and compatibility requirements; no public internal NRSC SOP with labour minutes was found.
5. Inspect changes, calculate area where required and issue a map/report. Bhuvan supports historical comparison (e.g. Cartosat mosaics for 2010–09 and 2016), but does not document a natural-language agentic change workflow. [NRSC/Bhuvan](https://www.nrsc.gov.in/nrscnew/).

Decision impact: describe a multi-stage manual workflow, without invented duration.

## Q3. Data-access reality

| Source | Programmatic access / authentication | Licence, restriction and 48-hour reality |
|---|---|---|
| Bhoonidhi | Portal download. No official REST/OGC/STAC API located. Registration is explicit. | GSD >=5 m is open/free to registered users, “as is where is.” Approval time, nationality policy, quotas and API access are **[UNVERIFIED]**. [Terms](https://bhoonidhi.nrsc.gov.in/bhoonidhi/htmls/TnC.html) |
| Bhuvan | Documented OGC WMS/WMTS; map-service access, not proof of unrestricted source-raster download. | No public rate limit, student-key or foreign-account policy found. WMS appears keyless; other access **[UNVERIFIED]**. [WMS guide](https://bhuvan.nrsc.gov.in/wiki/index.php/How_to_use_WMS_services) |
| MOSDAC | Public portal, but no official REST/STAC API, rate limits or terms for derivatives were verified. | Student key within 48 hours: **[UNVERIFIED]**. |
| Copernicus / Sentinel-2 | OData, STAC, Sentinel Hub Catalog and openEO. STAC is `https://stac.dataspace.copernicus.eu/v1/`; Sentinel-2 L1C/L2A are listed. | Standard account: 2,000 S3/OData/STAC requests/min, four concurrent connections, 20 MB/s/connection, 12 TB rolling-30-day transfer before throttling. Commercial services are permitted. Approval/nationality details not found. [APIs](https://dataspace.copernicus.eu/analyse/apis), [STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html), [quotas](https://documentation.dataspace.copernicus.eu/Quotas.html), [FAQ](https://documentation.dataspace.copernicus.eu/FAQ.html) |

Sensor/product latency was not verified for all four sources. Sentinel-2 is an optical multispectral fallback, not a RISAT-SAR substitute or evidence of hidden-set performance.

Decision impact: use public benchmarks/Sentinel as safe fallback; secure ISRO data access early.

## Q4. Model landscape as of September 2026

No open-weight model was verified here as jointly supporting raw multispectral bands and SAR, while reporting reproducible results across VRSBench, RSVQA and CDVQA. That absence is material.

VRSBench has 29,614 images, 29,614 human-verified detailed captions, 52,472 object references and 123,221 QA pairs for captioning, grounding and VQA. [NeurIPS paper](https://proceedings.neurips.cc/paper_files/paper/2024/file/05b7f821234f66b78f99e7803fffa78a-Paper-Datasets_and_Benchmarks_Track.pdf). RSVQA has HR/LR subsets; CDVQA is the PS-mandated change-VQA evaluation.

* **Qwen2.5-VL 3B/7B/72B.** A 2026 RS-VQA comparison reports average accuracy across VRSBench, MME-RealWorld-RS, XLRS-Bench and LRS-VQA of 23.2/29.1/34.6% respectively. It does not establish native raw SAR/multispectral input, CDVQA scores or a fixed VRAM figure. [Comparison](https://www.mdpi.com/2072-4292/18/14/2288).
* **GeoChat.** The same comparison reports 29.3% average. It does not establish raw-band/SAR support. [Comparison](https://www.mdpi.com/2072-4292/18/14/2288).
* **GeoLLaVA-8K.** The same comparison reports 39.6% average, but does not demonstrate native SAR/multispectral or CDVQA capability. [Comparison](https://www.mdpi.com/2072-4292/18/14/2288).
* **RSCoVLM 7B.** A 2026 paper reports 94.30 RSVQA and 95.80 VRSBench accuracy under its protocol. Licence, CDVQA score, native SAR/multispectral support and reproducible VRAM remain **[UNVERIFIED]** here. [Paper](https://doi.org/10.3390/rs18020222).

Ranked by evidence: a quantised 3B/7B VLM plus specialist raster/SAR tools is the practical consumer-GPU demo option; remote-sensing 7B models are citeable only after licence/reproduction verification; no single native multi-band/SAR VLM deserves a high-confidence rank. No Indian-language or public ISRO-specific evaluation set was found; ISRO/SAC’s set is undisclosed.

Decision impact: demonstrate orchestration and specialist tools rather than claim a single VLM natively understands all bands/SAR.

## Q5. Known failure modes

The PS’s adaptation/specialist-routing requirement is evidence that a generic VLM is insufficient. Quantified real-world RS-VQA variation is clear: GPT-4o reports 42.5% on VRSBench versus 28.9% MME-RealWorld-RS; Qwen2.5-VL-7B 33.8% versus 28.4%; GeoChat 40.8% versus 28.6%. The benchmark attributes high-resolution difficulty to sparse informative content, background redundancy and large scale variation. [Results](https://www.mdpi.com/2072-4292/18/14/2288).

This supports object-scale/small-object sensitivity, not a general hallucination-rate claim. VRSBench was created partly because prior datasets lacked detailed-object or high-quality annotations. [VRSBench](https://arxiv.org/abs/2406.12384). Measured evidence for absolute geolocation, ground-sample-distance grounding, temporal reasoning, multispectral beyond RGB and counting was not verified in this review; each is **[UNVERIFIED]**.

Decision impact: show boxes/masks, dates and GSD; do not claim exact counting, location or raw-band competence without task-specific tests.

## Q6. Feasibility numbers

Published India-hosted cloud rates:

* IndiaAI Compute Portal: A100 40 GB, ₹136/GPU-hour on-demand; ₹81/GPU-hour at 12-month reservation. [Price list](https://compute.indiaai.gov.in/pricelist).
* E2E, which states it is MeitY-empanelled: A100 40 GB ₹179/hour, L4 24 GB ₹49/hour, L40S 48 GB ₹102/hour, A100 80 GB ₹189/hour. [Price list](https://www.e2enetworks.com/gpu-cloud).
* Derived continuous annual A100-40GB cost: ₹136 x 8,760 = **₹1,191,360/year**; at ₹81/hour, ₹81 x 8,760 = **₹709,560/year**. These exclude storage, egress, CPU, support and taxes.
* IndiaAI publicly says approved users may obtain compute below ₹100/hour after subsidy; this is not a universal production price. [PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2097709&lang=2&reg=3).

NICSI’s 2025 cloud provider RFE was found but no retrieved GPU line item; NIC/NICSI GPU price is **[UNVERIFIED]**. [NICSI notice](https://nicsi.nic.in/viewNoticeArchive?fileName=2025_NICSI_237065_1.pdf). No reliable public award value for a suitable on-prem server, or staffing benchmark for this system, was verified.

Decision impact: pilot cloud operating cost can be bounded; capex and staffing must stay “quote/department decision required.”

## Q7. EO-specific regulatory stack

Indian Space Policy 2023 directly applies. NRSC says GSD >=5 m data is free/open, while <5 m data is free for government entities and fairly/transparently priced for NGEs. [NRSC policy](https://www.nrsc.gov.in/nrscnew/pnp_order_policy.php). Bhoonidhi implements this for registered users. [Terms](https://bhoonidhi.nrsc.gov.in/bhoonidhi/htmls/TnC.html).

The 2021 DST geospatial guidelines cover satellite remote sensing and liberalise acquisition/production of geospatial data, superseding contrary earlier guidelines. [DST guidelines](https://geospatial.dst.gov.in/Guidelines.aspx). They do not override source licence, security classification or DoS controls.

CERT-In directions under IT Act section 70B require government organisations to enable logs and keep them securely within Indian jurisdiction for 180 days; cloud/VPS/data-centre providers retain specified customer information for five years. [CERT-In directions](https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf). DPDP matters where imagery, prompts/logs or products identify a person, but is not the primary EO-data rule.

No public material located grants permission for DoS to transmit imagery/derivatives to a foreign-hosted LLM API, nor establishes an absolute blanket ban. The defensible conclusion is **[UNVERIFIED / explicit deployment authorisation required]**: classify data, comply with NRSC/Bhoonidhi terms, and obtain DoS security/procurement approval. Indian-jurisdiction log retention alone does not prove raw imagery can leave India.

Decision impact: treat foreign hosted APIs as unavailable until written DoS approval; design for local or approved India-hosted inference.

## Q8. Prior art

Bhuvan already provides discovery, visualisation, thematic layers, downloads and OGC services. It does not publicly document the required agentic natural-language routing across VQA, grounding, bitemporal change and co-registered optical–SAR analysis with an audit trace. [Bhuvan WMS](https://bhuvan.nrsc.gov.in/wiki/index.php/How_to_use_WMS_services).

Copernicus Data Space provides catalogue, browser, download and processing APIs; it is data infrastructure rather than an ISRO-specific SatQuery system. [CDSE APIs](https://dataspace.copernicus.eu/analyse/apis). Open VLM research covers parts of captioning, grounding and VQA, but does not remove the PS’s adaptation, paired-modality, GeoTIFF/TIFF and agentic-trace requirements. [VRSBench](https://arxiv.org/abs/2406.12384).

Commercial geospatial AI was not included because authoritative, comparable Indian-government price/licence evidence was not verified. Claiming incumbents cannot solve the task would be speculation.

Decision impact: differentiate on the exact PS evaluation scope and auditable integration, not on an assertion that ISRO lacks GIS/AI tools.

## Disconfirmation

1. **“This is Bhuvan plus a chat front end.”** Strong: Bhuvan already offers thematic layers, historical imagery and OGC services. It is wrong only if the system improves required benchmark tasks and supplies evidence-backed routing across GeoTIFF/TIFF pairs, rather than a chat UI.
2. **“The team uses RGB web-image models against a hidden Cartosat-2S/RISAT test.”** Strong: PS explicitly names RISAT SAR; the evidence above does not establish native raw SAR/multispectral competence. It is wrong only with end-to-end held-out co-registered optical/SAR testing, documented preprocessing and failure cases.
3. **“Foreign APIs are a security/procurement trap; local inference will be too weak.”** Strong: data-export authorisation was not found and CERT-In requires Indian-jurisdiction logs. It is wrong only with DoS approval or locally/India-hosted measured inference meeting security and performance requirements.

## Final decision table

| Finding | Confidence | Build decision affected | What changes if true |
|---|---|---|---|
| PS mandates adapted VLM, VQA, another single-image task, change and optical–SAR analysis, visible agent trace | High | Demo scope | Omission becomes a compliance failure |
| Live submission count is unverified | Low | Differentiation narrative | Remove numerical field claim |
| Bhuvan has OGC services and thematic layers | High | Before workflow | Position against fragmented analysis, not absence of tools |
| No public manual turnaround metric | High | Time-saving claim | Use no time-saving number |
| Sentinel-2 CDSE APIs/quotas are documented | High | Data fallback | Use optical demo fallback, not hidden-set equivalence |
| No verified native open VLM handles raw multispectral and SAR jointly | Medium | Architecture | Orchestrate specialist raster/SAR tools |
| A100-40GB pricing is ₹81–₹179/hour depending on provider/commitment | High | Feasibility | Bound cloud pilot costs only |
| Foreign LLM API authorisation is unverified | High | Deployment | Need DoS approval or approved India/local inference |
