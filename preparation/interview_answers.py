"""Model answers shown with each company interview question."""

ANSWERS = {
    "Tell me about a time you solved a complex technical problem.": (
        "Pick one incident with a clear constraint, such as a failing service during a release. "
        "Explain how you isolated the cause with logs, metrics, and a small reproduction, then the fix you shipped. "
        "State the result in numbers, for example latency or error rate, and the guardrail you added so it would not recur. "
        "Close with what you would do sooner next time."
    ),
    "How would you design Google Search autocomplete?": (
        "Start with a prefix trie or a weighted radix tree of popular queries, kept in memory and refreshed from search logs. "
        "Score suggestions by frequency, recency, personal history, and language, and filter unsafe or zero-result phrases. "
        "Serve the top suggestions from an edge cache with a tight latency budget, and fall back to a broader index when the prefix is rare. "
        "Measure keystroke latency, suggestion click-through, and the rate of abandoned queries."
    ),
    "Explain the concept of MapReduce and when you would use it.": (
        "MapReduce splits a large input across workers. Each map task emits key-value pairs, shuffle groups them by key, and reduce aggregates each group. "
        "Use it for batch work that is too big for one machine, such as counting tokens, joining logs, or building an inverted index. "
        "Prefer a newer engine such as Spark when you need iterative jobs, but the same split-group-aggregate idea still applies. "
        "It is a poor fit for low-latency requests or workloads that need constant small updates."
    ),
    "Describe a situation where you had to deal with ambiguity.": (
        "Describe a project where the goal was clear and the requirements were not, such as an undefined success metric. "
        "Say how you wrote down assumptions, asked the decision maker which outcome mattered, and shipped a small version to learn. "
        "Show that you made a decision with a review date rather than waiting for perfect clarity. "
        "End with the outcome and which assumption turned out to be wrong."
    ),
    "How would you design a URL shortener like goo.gl?": (
        "Accept a long URL, generate a short key with a base-62 encoding of a unique id, and store the mapping in a durable key-value store. "
        "Redirect with an HTTP 302, cache hot keys at the edge, and rate-limit creation to stop abuse. "
        "Add expiry, analytics counts, and a check that the destination is not on a malware list. "
        "Plan for key collisions, read-heavy traffic, and a way to delete a link without breaking the id sequence."
    ),
    "What is your approach to code reviews?": (
        "Read the change for intent first, then correctness, tests, and clarity. "
        "Comment on behavior and risk, and leave style to the formatter. "
        "Approve when you would be comfortable owning the code, and ask for a smaller patch when the diff mixes unrelated work. "
        "Respond to review on your own changes by fixing the issue or explaining the trade-off, not by defending the first draft."
    ),
    "How do you prioritize tasks when working on multiple projects?": (
        "Rank work by user impact and deadline, then by what unblocks other people. "
        "Make the order visible in the tracker and confirm it with the people waiting. "
        "Protect a daily block for the highest item and treat new requests as a swap, not an addition, unless the priority truly changes. "
        "Say how you communicate a slip early, with a new date, instead of going silent."
    ),
    "Design a real-time collaborative editing system like Google Docs.": (
        "Give each client a local copy and send operations, not full documents, over a persistent connection. "
        "Use operational transformation or CRDTs so concurrent edits converge, and keep a central log for history and permissions. "
        "Presence, cursors, and comments are separate lightweight channels. "
        "Store snapshots plus the operation log, and measure sync delay, conflict rate, and time to recover after a disconnect."
    ),
    "Explain how garbage collection works in your preferred language.": (
        "In Python, reference counting frees an object when its count hits zero, and a cycle collector handles loops the count cannot see. "
        "Allocation comes from pools of small objects, and collection pauses the threads that own those objects. "
        "You still create pressure with large temporary lists, global caches, and reference cycles through closures. "
        "I would show this with a memory profile before and after removing a retained cache, rather than calling gc.collect in production as a fix."
    ),
    "Tell me about a time you disagreed with a team member.": (
        "Choose a disagreement about a technical choice, not a personality. "
        "Say what each of you optimized for, the evidence you brought, and how you decided, including when you changed your mind. "
        "Show that the working relationship stayed intact and the decision was written down. "
        "Avoid a story where you were entirely right and the other person was simply stubborn."
    ),
    "Tell me about a time you delivered results under tight deadlines.": (
        "Set the scene with the date, the scope, and why the date could not move. "
        "Explain what you cut, what you kept, and how you checked the risky path first. "
        "Give the result that shipped and the follow-up you scheduled for the work you deferred. "
        "Amazon will listen for ownership: you raised the risk early and you stayed with the outcome after launch."
    ),
    "How would you design Amazon's recommendation system?": (
        "Collect views, purchases, and returns as events, and build both item-to-item similarity and a model of the shopper. "
        "Generate candidates from those signals, then rank them with a model that balances relevance, margin, and availability. "
        "Serve the ranked list from a low-latency store, and keep a fallback of popular items in that category. "
        "Evaluate offline with holdout purchases and online with click and conversion, and watch for feedback loops that only promote already popular products."
    ),
    "Describe a time when you had to make a decision with incomplete data.": (
        "Name the decision, the data you had, and the data you could not get in time. "
        "Explain the reversible choice you made, the signal that would tell you it was wrong, and when you would revisit it. "
        "Share the outcome honestly, including a correction if the first call was off. "
        "The point is a reasoned bet, not a claim that you never need data."
    ),
    "How would you design a system to handle Black Friday traffic?": (
        "Find the read and write paths that spike, and cache product pages and inventory snapshots ahead of the sale. "
        "Autoscale stateless services, put a queue in front of order processing, and shed non-critical work such as recommendations. "
        "Run a load test at the expected peak, set clear error budgets, and keep a feature flag to disable heavy pages. "
        "Protect checkout correctness over homepage freshness, and plan a rollback that does not lose placed orders."
    ),
    "Tell me about your most challenging project and how you handled it.": (
        "Choose a project that was hard for a specific reason: scale, a new domain, or a dependency you did not control. "
        "Walk through the plan, the point where the plan failed, and the change you made. "
        "Quantify the result and name the people you pulled in. "
        "Finish with the practice you kept, such as smaller milestones or an earlier prototype."
    ),
    "Explain the CAP theorem and its implications.": (
        "A distributed store can guarantee at most two of consistency, availability, and partition tolerance, and partitions happen, so the real choice is between consistency and availability during a split. "
        "A bank ledger should refuse a write it cannot confirm. A product catalog can serve a slightly stale page. "
        "Say which choice your system makes, and how clients detect a stale or rejected response. "
        "CAP does not remove the need for timeouts, retries, and a clear conflict rule."
    ),
    "What does customer obsession mean to you?": (
        "It means starting from the customer's job, not from the feature list. "
        "I would cite a time you changed a design because support tickets or a usability session showed the planned flow was wrong. "
        "Include a trade-off you accepted, such as more engineering time, to remove a step the customer kept failing. "
        "Tie it to a metric the customer feels, such as time to complete checkout, not only an internal score."
    ),
    "Design a distributed caching system.": (
        "Put a cache in front of the source of truth, key it by the read query, and set a TTL plus explicit invalidation on writes. "
        "Shard by key, replicate hot keys, and use single-flight requests so a miss does not stampede the database. "
        "Decide what happens on failure: serve stale data or fail the request. "
        "Track hit rate, eviction, and p99 latency, and never cache a response that is unique per user unless the key includes the user."
    ),
    "How would you improve the efficiency of a slow database query?": (
        "Read the query plan before changing anything. "
        "Look for a sequential scan, a missing index that matches the filter and order, or a join that multiplies rows. "
        "Add the smallest index that fits the predicate, or rewrite the query to filter earlier, and compare the plan and the runtime on production-like data. "
        "If the table is huge, consider a summary table or a read replica, and confirm the change with the slow-query log after release."
    ),
    "Describe a time you took ownership of a problem outside your scope.": (
        "Describe a gap that was hurting users and had no clear owner, such as a broken handoff between two teams. "
        "Say what you did yourself, who you informed, and how you handed the lasting fix to the right owner. "
        "Show the result and that you did not silently absorb the work forever. "
        "Ownership here is closing the loop, including the communication."
    ),
    "How would you design Microsoft Teams?": (
        "Separate identity, messaging, presence, meetings, and files. "
        "Chat is a durable log per conversation with fan-out to members. Meetings use a media service for audio and video, with chat and recording beside it. "
        "Presence is ephemeral and can be slightly stale. Files stay in a document store and are linked, not copied into every message. "
        "Design for tenants, retention, and a client that keeps working through a brief disconnect, then reconcile."
    ),
    "Describe a time you mentored someone.": (
        "Name the person's level and the skill they needed, without making the story about your status. "
        "Explain the concrete help: a weekly review of their design, paired debugging, or a written checklist. "
        "Show their result, such as shipping a feature alone or leading the next incident. "
        "Mention how you stepped back so they made the decisions."
    ),
    "Explain the difference between processes and threads.": (
        "A process has its own memory space and resources. Threads inside a process share that memory and can communicate by reading the same data, which is fast and easy to get wrong. "
        "Processes crash in isolation and need pipes, sockets, or shared memory to talk. "
        "Use threads for parallel work on shared state when you can lock it correctly. Use processes when you want isolation or to escape a runtime that does not run threads in parallel. "
        "Both still need a plan for shared resources, cancellation, and failure."
    ),
    "How do you handle technical debt in your projects?": (
        "Name the debt in the backlog with the user or developer cost, not as a vague cleanup ticket. "
        "Fix debt that sits on the path you are about to change, and schedule the rest against a visible budget so it is not only done in leftover time. "
        "Avoid a rewrite with no milestone. "
        "Give an example where paying the debt down made a later feature smaller."
    ),
    "Design a file synchronization service like OneDrive.": (
        "Split files into chunks, hash each chunk, and upload only the chunks that changed. "
        "Keep a per-user metadata log of versions, and let each device pull the log and reconcile. "
        "Conflicts become two versions the user can see, rather than a silent overwrite. "
        "Encrypt content, scan for malware, and design the client to pause and resume on a flaky network."
    ),
    "What is dependency injection and why is it useful?": (
        "Dependency injection means a function or object receives the services it uses, instead of constructing them itself. "
        "That makes the dependency explicit and lets a test pass a fake database or clock. "
        "It also lets one composition root choose the real implementations for production. "
        "It is not useful when it hides a simple call behind a container nobody can trace."
    ),
    "Tell me about a time you had to learn a new technology quickly.": (
        "Name the technology and the deadline that forced the learning. "
        "Describe how you learned just enough to ship: the official tutorial, one small prototype, and a person who already knew it. "
        "Say what you delivered and what you later learned you had misunderstood. "
        "Keep the story about the method, not a claim that you mastered it in a day."
    ),
    "How would you design an email system?": (
        "Accept mail through SMTP, write it to a durable queue, and have workers store the message and update each recipient's mailbox index. "
        "Serve read and search from that index, and keep attachments in object storage. "
        "Add spam scoring, authentication checks, and retries with backoff for downstream delivery. "
        "Plan for huge inboxes, search latency, and a way to delete or hold a message for compliance."
    ),
    "Explain RESTful API design principles.": (
        "Model the API as resources with stable URLs, and use HTTP methods for the action: GET reads, POST creates, PUT or PATCH updates, DELETE removes. "
        "Use status codes that match the outcome, and keep requests stateless so any server can handle them. "
        "Paginate lists, version the contract when you break it, and document errors in a consistent body. "
        "REST is a constraint on the interface, not a requirement to expose your database tables."
    ),
    "Describe how you would debug a production issue.": (
        "Start from the symptom and the time it began, then check recent deploys, error rate, and saturation. "
        "Follow one failing request through logs and traces until you see the broken hop. "
        "Mitigate first if users are affected, with a rollback or a flag, then fix the cause and add a test or alert that would have caught it. "
        "Write down the timeline while it is fresh."
    ),
    "How would you design Facebook's News Feed?": (
        "Fan out new posts to the followers' feeds when the author is not huge, and fan in at read time for celebrities so one post does not write to millions of inboxes. "
        "Rank the candidate posts with a model using affinity, freshness, and content type, and apply integrity checks before display. "
        "Store the ranked feed in a cache per user and refresh it as they scroll. "
        "Measure time to first story, ranking quality, and the cost of a single viral post."
    ),
    "Tell me about a time you moved fast and broke things.": (
        "Use a story where speed created a real defect, and you noticed it quickly. "
        "Explain the shortcut, the blast radius, and the fix you shipped the same day. "
        "Then say what guard you added, such as a test or a staged rollout, so the next fast change was safer. "
        "The useful ending is the lesson, not pride in the breakage."
    ),
    "Explain the concept of eventual consistency.": (
        "After a write, different readers may briefly see different values, and they converge once replication catches up. "
        "It is a fit for likes, feeds, and profile caches, where a short delay is acceptable. "
        "It is a poor fit for a balance or a seat inventory unless you add a stronger check at the moment of commit. "
        "Clients should tolerate a stale read and should retry with the same idempotency key so a repeat write is safe."
    ),
    "How do you approach building products at scale?": (
        "Find the one path that must stay fast and correct, and make everything else degradable. "
        "Measure before you split services, and add caches, queues, and limits at the boundary that is actually hot. "
        "Roll out by cohort, watch the error budget, and keep a simple fallback. "
        "Scale is a series of explicit trade-offs, not a stack of tools."
    ),
    "Design an Instagram-like photo sharing service.": (
        "Store the original image in object storage, generate a few display sizes asynchronously, and save the metadata and follower graph in a database. "
        "The feed uses the same fan-out pattern as a news feed, with a CDN in front of the images. "
        "Likes and comments can be eventually consistent. Uploads need virus scanning, size limits, and a privacy check before a URL is public. "
        "Track upload success, time until the image is visible to followers, and CDN hit rate."
    ),
    "What is your experience with A/B testing?": (
        "Define the metric and the guardrail metrics before the test, and compute the sample size so you are not peeking at noise. "
        "Randomize by user, keep the variants equivalent except for the change, and run until you hit the planned sample or a pre-set harm threshold. "
        "Ship the winner only when the lift is real and the guardrails held. "
        "Mention a test you stopped or a result that did not match the hypothesis."
    ),
    "Describe a time you had to make a tough product decision.": (
        "Frame the two options and who each one served. "
        "Say which evidence you used, the option you rejected, and the cost of that rejection. "
        "Show how you told the people who disagreed, and how you checked after launch whether the call was right. "
        "A tough decision has a real downside you accepted on purpose."
    ),
    "How would you design a chat messaging system?": (
        "Give each conversation an id and append messages to a log. Deliver them over a persistent connection, and store them for history and search. "
        "Unread counts and read receipts are separate small records. "
        "Use a queue so a slow recipient does not block the sender, and keep a copy on the device for offline reading. "
        "Plan for ordering, duplicate sends, media uploads, and blocking or reporting a user."
    ),
    "Explain how DNS works.": (
        "A resolver asks for a name. If it has no fresh answer, it queries a root server, then a top-level domain server, then the authoritative server for that zone. "
        "The answer is an IP address or another record, cached for the TTL. "
        "A name can point at several addresses for load spreading, and a CNAME adds an extra lookup. "
        "Failure usually looks like a stale cache, a wrong record, or a resolver that cannot reach the authoritative server."
    ),
    "Tell me about a time you improved a process or system.": (
        "Start from the pain: how long the old path took, or how often it failed. "
        "Describe the smallest change that removed a step, such as a script, a checklist, or a default in the tool. "
        "Give the before and after measurement. "
        "Note how you got other people to use it, because an unused improvement is not an improvement."
    ),
    "How would you design the App Store?": (
        "Developers upload a build, you scan and review it, then publish metadata and binaries to a catalog. "
        "Clients query that catalog, download through a CDN, and the device checks the signature before install. "
        "Purchases go through a payment service that records entitlements, so a reinstall can restore them. "
        "Design review queues, regional pricing, version rollback, and a kill switch for a harmful app."
    ),
    "Tell me about a product you love and how you would improve it.": (
        "Name a specific product and the job you hire it for. "
        "Praise one concrete behavior, then one friction you hit repeatedly. "
        "Propose a change a team could ship, and say how you would know it worked, such as fewer support contacts or a shorter task time. "
        "Avoid a vague wish list. One sharp improvement is stronger."
    ),
    "Explain memory management in iOS/macOS.": (
        "Swift and modern Objective-C use automatic reference counting. Each strong reference increments a count, and the object is freed when the count reaches zero. "
        "Cycles between objects leak unless one side is weak or unowned. "
        "Closures capture self strongly by default, which is a common cycle. "
        "I would find that with the memory graph debugger, break the cycle, and confirm the object deallocates when the screen closes."
    ),
    "How do you ensure code quality in your projects?": (
        "Agree on a small set of checks that run before merge: tests for the behavior, a linter, and a review by someone who understands the area. "
        "Keep the tests close to the risk, and fix a broken main branch before adding features. "
        "Use production alerts for the failures tests cannot see. "
        "Quality is the habit of not merging what you cannot explain."
    ),
    "Design a music streaming service like Apple Music.": (
        "Store tracks and artwork in object storage, and serve them through a CDN with adaptive bitrate so a weak network steps down instead of stalling. "
        "Keep a catalog for search and a separate store for playlists, likes, and downloads. "
        "Rights and regional availability are checked before a URL is issued. "
        "Offline mode stores encrypted files tied to the account, and you measure start-up time, rebuffer rate, and failed plays."
    ),
    "What is your approach to accessibility in software design?": (
        "Treat it as a requirement in the design, not a pass at the end. "
        "Use semantic controls, visible focus, sufficient contrast, and labels that a screen reader can announce. "
        "Support keyboard use and respect reduced-motion settings. "
        "Check with an automated scanner and with one real assistive-technology pass, and fix the issues that block a task, not only the ones that change a score."
    ),
    "Describe a time you had to balance quality with speed.": (
        "State the deadline and the quality bar you refused to drop, such as data loss or a broken payment. "
        "Say what you simplified: fewer edge cases, a manual step, or a flag that limited the audience. "
        "Show the release and the follow-up that restored the deferred quality. "
        "The answer should make the trade-off explicit."
    ),
    "How would you design Siri's backend?": (
        "Capture audio on the device, detect the wake phrase locally when possible, and send the utterance to a speech service. "
        "An intent parser turns the text into a structured request and routes it to a domain service such as music, maps, or home. "
        "Keep personal context in a permissioned profile, and return a short spoken response plus an action. "
        "Design for privacy, a low time-to-first-word, and a graceful failure when the intent is ambiguous."
    ),
    "Explain the MVC design pattern.": (
        "The model holds the state and the rules. The view draws that state. The controller takes input and tells the model what to change. "
        "The split keeps display code from owning business rules, and lets you test the model without a screen. "
        "On Apple platforms the controller often grows until it also fetches data and formats strings, which is the pattern failing. "
        "I keep the model testable and move formatting into a small presenter when a controller starts doing both."
    ),
    "Tell me about a time you advocated for the user.": (
        "Describe a decision that was convenient for the company and costly for the user, such as an extra confirmation or a hidden fee. "
        "Say what evidence you brought, the change you asked for, and whether you won. "
        "If you lost, say how you reduced the harm anyway. "
        "Keep the user specific: a task they could not finish, not a general persona."
    ),
    "How would you design Netflix's streaming architecture?": (
        "Encode each title into several bitrates and store the segments on a CDN close to the viewer. "
        "The client picks the next bitrate from buffer health and bandwidth. A control service handles accounts, recommendations, and which CDN to use. "
        "Playback authorization is a short-lived token so a URL cannot be shared forever. "
        "Measure rebuffering, start time, and the share of traffic served from the edge rather than the origin."
    ),
    "Tell me about a time you took a risk that paid off.": (
        "Define the risk in advance: what you might have lost, and why the upside was worth it. "
        "Explain the limit you set, such as a canary or a time box, so the downside was contained. "
        "Give the result with a number. "
        "A good risk story includes the point at which you would have stopped."
    ),
    "Explain content delivery networks (CDNs).": (
        "A CDN caches copies of content at locations near users. The first request may miss and fetch from the origin. Later requests in that region are served locally. "
        "That cuts latency and origin load for images, video segments, and static files. "
        "You control freshness with cache headers and explicit purges. "
        "Dynamic, per-user responses usually should not be cached unless the cache key includes the user and the content is safe to store."
    ),
    "How do you approach microservices architecture?": (
        "Split a service when a team needs to deploy and scale it on its own cadence, and when the boundary matches a business capability. "
        "Each service owns its data. They talk through explicit APIs or events, and a failure in one must not take down the rest. "
        "Start with a well-structured application and extract the piece that is actually constrained. "
        "The cost is operational: tracing, contracts, and data that is no longer in one transaction."
    ),
    "Design a recommendation engine for movies.": (
        "Use watch history, ratings, and similar viewers to generate candidates, then rank them with a model that also knows time of day and what is newly available. "
        "Keep a cold-start path of popular and critically strong titles for a new account. "
        "Filter titles the account cannot play in that region. "
        "Evaluate with offline ranking metrics and with online watch time, and stop a row that only repeats what the person just finished."
    ),
    "How would you design Uber's ride matching system?": (
        "Track driver locations in a geospatial index and, on a request, search a radius that widens if nobody is free. "
        "Score candidates by ETA, direction, and acceptance history, offer the trip to the best driver, and move to the next if they decline. "
        "Write the match as a single assignment so two riders cannot take the same driver. "
        "Measure match time, cancellation, and extra driving before pickup, and degrade by widening the radius rather than failing the request."
    ),
    "Tell me about a time you optimized a system for performance.": (
        "Start with the measurement that showed the problem, not with the tool you wanted to use. "
        "Identify the hottest function, query, or round trip, change that one thing, and show the before and after latency or cost. "
        "Mention a trade-off, such as more memory for a cache. "
        "Say how you kept the improvement, with a benchmark or an alert, so it did not quietly regress."
    ),
    "Explain the concept of load balancing.": (
        "A load balancer spreads requests across healthy servers so no single machine takes the whole traffic. "
        "Simple methods include round robin and least connections. Smarter ones use latency or a consistent hash when the same client should stick to one server. "
        "Health checks remove a bad instance. "
        "The balancer itself must be redundant, and it should not hide a downstream that is timing out by retrying so hard that it makes the outage worse."
    ),
    "How do you handle real-time data processing?": (
        "Ingest events into a log, process them in small windows, and publish results to a store the product can read. "
        "Keep the processing idempotent so a replay does not double-count. "
        "Separate the hot path, such as a live location or a price, from batch jobs that can be minutes late. "
        "Alert on consumer lag, because a real-time system that falls behind is just a slow batch system."
    ),
    "Design a surge pricing algorithm.": (
        "Compare open requests with free drivers in a small geographic cell over a short window. "
        "When demand exceeds supply, raise the price in steps, show it before the rider confirms, and cap it. "
        "Lower it as soon as the cell recovers, and do not let a single cell's spike jump neighboring cells without a reason. "
        "Watch acceptance rate and completed trips. A price that only increases cancellations has failed."
    ),
    "How would you design LinkedIn's connection suggestion system?": (
        "Generate candidates from shared employers, schools, mutual connections, and people the member already viewed. "
        "Rank them with a model trained on who accepted a request, and down-rank people the member dismissed. "
        "Respect privacy: do not reveal a suggestion that leaks a hidden profile view. "
        "Precompute suggestions for active members and refresh them when a new connection changes the graph."
    ),
    "Tell me about a time you influenced without authority.": (
        "Describe a change you needed from a team you did not manage. "
        "Explain their concern, the evidence or prototype you used, and the ask you made smaller so they could say yes. "
        "Show the outcome and how you shared the credit. "
        "Influence here is alignment, not a story about talking someone into something they still opposed."
    ),
    "Explain graph databases and their use cases.": (
        "A graph database stores entities as nodes and relationships as edges, so a question like friends-of-friends is a traversal rather than a chain of joins. "
        "They fit social connections, fraud rings, and dependency maps. "
        "They are a weak default for simple tabular reporting or heavy aggregations across every node. "
        "I would use one when the product's main queries walk relationships of unknown depth."
    ),
    "How do you approach data privacy in your designs?": (
        "Collect the smallest set of fields that the feature needs, and state why each one is there. "
        "Separate identifiers from content, encrypt sensitive data, and limit who can query it. "
        "Support deletion and export, and keep retention short for logs that are not required. "
        "A design review should ask what happens if this table leaks, and remove fields that make that leak worse."
    ),
    "Design a professional networking feed.": (
        "Build the feed from the member's connections and follows, plus a small set of recommended posts. "
        "Rank by relationship strength, relevance to the member's skills, and freshness, and demote engagement bait. "
        "Store a per-member feed cache and update it when a close connection posts. "
        "Keep posts, reactions, and comments as separate records, and measure meaningful actions such as profile visits rather than only time on screen."
    ),
    "How would you design a trading platform?": (
        "Separate market data, order entry, and the matching engine. The engine must process orders for one instrument in a strict sequence and record every fill. "
        "Clients receive price updates on a fast channel and submit orders on a reliable one with idempotency keys. "
        "Risk checks run before an order reaches the book: buying power, position limits, and market status. "
        "Design for audit, exactly-once fills, and a halt switch. Speed matters, but a wrong fill is worse than a slow one."
    ),
    "Explain concepts of risk management in software.": (
        "Identify what can fail, how likely it is, and how bad it is, then spend effort on the high impact items. "
        "In software that means limits, timeouts, backups, access control, and a rollback, not only more features. "
        "For a financial system, add position limits, dual control on sensitive actions, and an audit log that cannot be edited quietly. "
        "Review the list when the system changes, because a new dependency is a new risk."
    ),
    "Tell me about a time you handled a high-pressure situation.": (
        "Set the stakes and the clock. Describe the first action you took to stabilize, then how you found the cause. "
        "Name who you updated and how often. "
        "End with the resolution and one change that makes the same pressure less likely, such as an alert or a runbook. "
        "Stay with the facts. Pressure stories fall apart when they become heroics."
    ),
    "How do you ensure data security in financial applications?": (
        "Encrypt data in transit and at rest, and keep keys in a managed store with access logged. "
        "Authenticate strongly, authorize every action against the account, and make sensitive changes require a second check. "
        "Tokenize card numbers so most services never see them. "
        "Audit reads and writes, patch dependencies, and test the backup restore. Security is the set of controls you can show, not a claim that the app is secure."
    ),
    "Design a real-time stock price alerting system.": (
        "Ingest ticks into a stream, and evaluate each user's rules against the symbols they watch. "
        "Keep rules in memory, sharded by symbol, so a price update touches only the users watching that symbol. "
        "Fire an alert once per condition until it resets, and deliver it through push, email, or a webhook with retries. "
        "Measure delay from tick to notification, and shed delayed alerts rather than sending a price that is already stale."
    ),
    "How would you design a collaborative design tool?": (
        "Store the document as a scene graph of objects, and sync edits as operations on those objects so two people can change different layers at once. "
        "Use the same conflict approach as a collaborative editor, and keep versions for undo and history. "
        "Render on the client from the local graph, and send only the operations. "
        "Assets such as images live in object storage. Presence shows who is on which object. Comments anchor to an object id, not a pixel that will move."
    ),
    "Tell me about your experience with creative problem solving.": (
        "Give one example where the obvious fix was blocked and you found another path. "
        "Show the constraint, the options you listed, and why you tried the one you chose, including a quick prototype. "
        "State the result. "
        "Creative here means a useful alternative, not a clever idea that never shipped."
    ),
    "Explain image compression algorithms.": (
        "Lossless compression, such as PNG, stores the exact pixels using patterns and repetition, so it suits screenshots and UI. "
        "Lossy compression, such as JPEG, discards detail the eye notices less, which is why photos get much smaller and why text looks bad if you compress it that way. "
        "Modern codecs such as WebP and AVIF use better prediction and usually smaller files at the same visual quality. "
        "Choose by content: lossless for sharp graphics, lossy for photographs, and always check the visual result at the size you will ship."
    ),
    "How do you approach cross-platform compatibility?": (
        "Define the behavior once and keep platform differences at the edges: input, storage, and notifications. "
        "Test the shared core on each target you claim to support, not only on the machine you develop on. "
        "Pin runtime versions and avoid APIs that exist on only one platform unless you wrap them. "
        "Document what you do not support. A clear boundary is better than a feature that almost works on one system."
    ),
    "Design a cloud-based document editing system.": (
        "Keep the document as operations plus periodic snapshots in object storage, with metadata and permissions in a database. "
        "Clients edit locally and sync operations. Sharing is an access-control list checked on every read and write. "
        "Export to PDF or Office formats as a background job. "
        "Version history lets a user restore without destroying the latest copy. Measure sync delay and failed saves."
    ),
    "How would you design a CRM system?": (
        "The core records are accounts, contacts, and activities, with a strict ownership and sharing model so one tenant never sees another. "
        "Pipelines are configurable stages on an opportunity, and automation runs when a record changes. "
        "Search, reporting, and email sync are separate services fed by events, so a heavy report does not slow the people updating deals. "
        "Design imports, audit history, and custom fields without letting a tenant change the schema in a way that breaks others."
    ),
    "Tell me about a time you improved customer satisfaction.": (
        "Start from the complaint or the score, with the specific task customers failed. "
        "Describe the change, such as clearer status or a shorter form, and how you released it. "
        "Give the before and after: fewer tickets, a higher rating, or a higher completion rate. "
        "Mention how you checked you had not improved the score by making the survey easier to skip."
    ),
    "Explain multi-tenant architecture.": (
        "One application serves many customers, called tenants. Data is isolated by a tenant id on every row, or by a separate schema or database when the customer requires it. "
        "A shared database is cheaper and needs ruthless query filters. A database per tenant isolates noisy neighbors and simplifies deletion, at a higher operational cost. "
        "Authentication maps a user to a tenant, and every request carries that tenant. "
        "The failure to avoid is a query that forgets the tenant filter."
    ),
    "How do you approach API versioning?": (
        "Add fields in a backward-compatible way and avoid breaking existing clients. "
        "When you must break a contract, publish a new version, run both for a stated period, and give clients a date and a migration note. "
        "Version in the URL or a header, and keep the version explicit in logs. "
        "The best versioning strategy is a change that does not need a new version."
    ),
    "Design a workflow automation system.": (
        "Let a user define a trigger, conditions, and actions, and store that definition as data, not as deployed code. "
        "A worker picks up the trigger event, evaluates conditions, and runs actions with retries and a visible log. "
        "Actions call other services through a narrow interface so a failing email send does not corrupt the record. "
        "Provide a test run, an audit of who changed the rule, and a way to pause a workflow that is looping."
    ),
    "How would you design a distributed database?": (
        "Partition rows by a key so each shard owns a range, and replicate each shard to a few nodes. "
        "Writes go to a leader for that shard, and followers serve reads that can tolerate a small lag, or you wait for a quorum when the read must be current. "
        "Rebalance when a shard grows, and use a consensus protocol so a leader failure does not fork the data. "
        "The hard parts are transactions that cross shards, membership changes, and a backup you have actually restored."
    ),
    "Tell me about a time you optimized database performance.": (
        "Name the query and the symptom, such as a page that took seconds. "
        "Show the plan you read, the index or rewrite you applied, and the runtime before and after on realistic data. "
        "Mention a side effect you checked, such as slower writes from the new index. "
        "If you also added a cache, say what you did so a write did not leave the cache wrong."
    ),
    "Explain ACID properties in databases.": (
        "Atomicity means a transaction fully commits or fully rolls back. Consistency means it leaves the database in a valid state according to its constraints. "
        "Isolation means concurrent transactions do not see each other's half-finished work, at the isolation level you chose. Durability means a committed write survives a crash. "
        "These are guarantees of one database transaction. Once you have two services, you no longer get them for free across both. "
        "Say which isolation level you use and why, because the default is part of the design."
    ),
    "How do you handle database migrations?": (
        "Write a migration that moves forward and, when you can, backward. Apply it in a step the running application can tolerate, such as adding a column before the code reads it. "
        "Back up first, run the change on a copy, and deploy the code only after the schema matches what that code expects. "
        "Large rewrites of a hot table should be online, in batches. "
        "Never edit a migration that has already run in production. Add a new one."
    ),
    "Design an enterprise resource planning system.": (
        "Model the shared records the company runs on: finance, inventory, orders, and people, with one chart of accounts and one item master. "
        "Each module writes through the same transaction boundaries so a shipment and its invoice cannot diverge. "
        "Integrations with banks, warehouses, and payroll are explicit interfaces with retries and reconciliation reports. "
        "Permissions are role based, every financial change is audited, and reporting reads from a replica so month-end does not lock the people entering orders."
    ),
    "How would you design a large-scale data processing pipeline?": (
        "Land raw events in immutable storage, then run validated batch or stream jobs that write curated tables. "
        "Each stage has a schema, a owner, and a check that fails the job when counts or null rates look wrong. "
        "Make jobs idempotent and partitioned by time so you can rerun a day without rewriting history. "
        "Orchestrate dependencies, alert on late data, and keep the raw layer so a bad transform can be recomputed."
    ),
    "Tell me about your experience with enterprise software.": (
        "Talk about a system with many users, permissions, and a long life, not a weekend prototype. "
        "Mention how you handled upgrades, audit, and a customer who could not move fast. "
        "Give one concrete delivery: a migration, an integration, or a performance fix in that environment. "
        "Show you respect backward compatibility and the people who operate the system after you leave."
    ),
    "Explain containerization and its benefits.": (
        "A container packages an application with its libraries and runs it in an isolated process using the host kernel. "
        "That makes the same artifact run on a laptop and in production, and lets you start many copies quickly. "
        "It is lighter than a virtual machine and weaker as a security boundary, so you still patch the image and limit its privileges. "
        "The benefit I care about is a reproducible deploy, not the container runtime itself."
    ),
    "How do you approach legacy system modernization?": (
        "Map the behavior that must not change, especially the data and the external contracts. "
        "Strangle the old system by routing one capability at a time to a new implementation, with the old path still available. "
        "Add tests around the behavior before you move it. "
        "Avoid a big-bang rewrite. Ship a thin slice, compare outputs, and only then retire the old path."
    ),
    "Design a cloud infrastructure monitoring system.": (
        "Collect metrics, logs, and traces from every service with a standard agent, and store recent data in a system built for time series. "
        "Dashboards show the golden signals: latency, traffic, errors, and saturation. Alerts fire on symptoms users feel, with a runbook linked. "
        "Keep cardinality under control so a label explosion does not take down the monitor. "
        "The monitor must have a path that still works when the system it watches is failing, including a heartbeat for the monitor itself."
    ),
}


def answer_for(question):
    """Return the model answer for a company interview question."""
    text = (question or "").strip()
    found = ANSWERS.get(text)
    if found:
        return found
    return (
        "Open with the direct answer, then the main steps or components, and the trade-off you would accept. "
        "Use one concrete example, say how you would measure success, and name the failure you would design for."
    )
