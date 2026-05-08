# Edge Cases for Mutual Fund FAQ Assistant

## Overview
This document outlines comprehensive edge cases for the Nippon India Mutual Fund FAQ Assistant project, covering all potential failure scenarios, boundary conditions, and exceptional situations that need to be handled for robust evaluation and testing.

---

## 1. Data Source & Scraping Edge Cases

### 1.1 Source Availability Issues
- **Complete Source Unavailability**: All official Nippon India websites down
- **Partial Source Failure**: Only some sources accessible (e.g., factsheet available but SID not)
- **Temporary Outages**: Source websites temporarily down during scheduled scraping
- **Rate Limiting**: Sources implement rate limiting blocking scrapers
- **Authentication Required**: Sources suddenly require login/captcha
- **Geographic Restrictions**: Sources block access from certain regions
- **SSL/TLS Issues**: Certificate problems preventing secure connections

### 1.2 Content Format Changes
- **Website Redesign**: AMC completely changes website structure
- **PDF Format Changes**: New PDF layout breaking existing parsers
- **Dynamic Content**: Sources switch to JavaScript-heavy content
- **API Deprecation**: Sources retire old APIs without notice
- **Mobile vs Desktop**: Different content served to different user agents
- **Content Gating**: Sources move content behind paywalls or registration

### 1.3 Data Quality Issues
- **Inconsistent Data**: Different sources showing conflicting information
- **Missing Critical Fields**: Essential data points (expense ratio, exit load) absent
- **Outdated Information**: Sources not updated with latest NAV/performance
- **Duplicate Content**: Same information repeated across multiple sources
- **Malformed Data**: Corrupted PDFs, broken tables, invalid formats
- **Encoding Issues**: Special characters, Unicode problems in scraped content

---

## 2. RAG System Edge Cases

### 2.1 Vector Store Issues
- **Empty Corpus**: No documents available for retrieval
- **Corrupted Embeddings**: Vector store contains invalid embeddings
- **Index Corruption**: Search index becomes corrupted or inconsistent
- **Dimension Mismatch**: New embeddings have different dimensions than stored ones
- **Memory Limits**: Vector store exceeds memory capacity
- **Concurrent Access**: Multiple processes trying to update vector store simultaneously

### 2.2 Retrieval Failures
- **No Relevant Results**: Query returns no matches from corpus
- **Too Many Results**: Query returns hundreds of irrelevant matches
- **Low Similarity Scores**: All results below relevance threshold
- **Context Window Overflow**: Retrieved context exceeds model token limit
- **Cross-Contamination**: Results from different funds mixed inappropriately
- **Temporal Mismatch**: Retrieving outdated information when recent data exists

### 2.3 Embedding Edge Cases
- **Empty Queries**: User submits empty or whitespace-only queries
- **Extremely Long Queries**: Queries exceeding token limits for embedding
- **Special Characters**: Queries with emojis, symbols, or non-English text
- **Ambiguous Queries**: Queries that could match multiple fund types
- **Typos and Misspellings**: User queries with spelling errors
- **Mixed Language Queries**: Queries mixing English and regional terms

---

## 3. LLM & Response Generation Edge Cases

### 3.1 Model Availability Issues
- **Groq API Downtime**: Complete Groq service unavailability
- **Rate Limit Exceeded**: Hitting Groq API rate limits
- **Model Unavailability**: Specific model (LLaMA-3) temporarily unavailable
- **Token Limits**: Queries or responses exceeding model token limits
- **Timeout Issues**: LLM responses taking too long to generate
- **Cost Overruns**: Unexpected high API costs due to usage patterns

### 3.2 Content Generation Failures
- **Advisory Content Detection Failure**: Model generates investment advice accidentally
- **Source Citation Missing**: Response generated without proper source link
- **Length Violations**: Responses exceeding 3-sentence limit
- **Factual Inaccuracy**: Model hallucinates information not in context
- **Multiple Sources**: Response includes more than one citation
- **Compliance Violations**: Generated content violates SEBI/AMFI guidelines

### 3.3 Response Format Issues
- **JSON Parsing Errors**: Malformed JSON responses from LLM
- **Missing Required Fields**: Response lacks source_url, last_updated, etc.
- **Invalid URLs**: Generated source URLs are malformed or non-existent
- **Date Format Issues**: Last updated dates in invalid formats
- **Encoding Problems**: Special characters breaking response formatting
- **Empty Responses**: LLM returns empty or null responses

---

## 4. Multi-threading & Session Management Edge Cases

### 4.1 Session Isolation Failures
- **Memory Leakage**: Sessions sharing data between threads
- **Thread ID Collisions**: Multiple users getting same thread ID
- **Session Corruption**: Thread state becomes corrupted or inconsistent
- **Resource Exhaustion**: Too many concurrent threads exhausting memory
- **Race Conditions**: Simultaneous access causing data corruption
- **Session Timeout**: Long-running sessions expiring unexpectedly

### 4.2 Concurrent User Scenarios
- **Maximum Threads Reached**: User tries to create 4th thread (limit is 3)
- **Thread Switching Issues**: Problems switching between active threads
- **Lost Messages**: Messages disappearing during thread switches
- **Duplicate Thread Creation**: Multiple threads created with same ID
- **Cross-Thread Pollution**: Messages appearing in wrong threads
- **Session Persistence**: Threads not persisting across page refreshes

### 4.3 Load Balancing Issues
- **Uneven Distribution**: All threads going to same server instance
- **Hotspot Creation**: Single thread overwhelming system resources
- **Deadlock Situations**: Threads waiting for each other indefinitely
- **Priority Inversion**: Low-priority threads blocking high-priority ones
- **Resource Starvation**: Some threads not getting CPU/memory
- **Cascade Failures**: One thread failure causing others to fail

---

## 5. API Gateway & Backend Edge Cases

### 5.1 Request Handling Failures
- **Malformed Requests**: Invalid JSON or missing required fields
- **Authentication Failures**: Invalid API keys or expired tokens
- **Method Not Allowed**: Wrong HTTP methods used
- **Content-Type Issues**: Wrong content types in requests
- **Header Problems**: Missing or invalid request headers
- **Payload Too Large**: Requests exceeding size limits

### 5.2 Response Failures
- **HTTP Error Codes**: 4xx/5xx errors from various services
- **Timeout Scenarios**: Services not responding within time limits
- **Partial Responses**: Incomplete or truncated responses
- **Encoding Mismatches**: Response encoding different from expected
- **Redirect Loops**: Infinite redirect chains
- **Service Dependencies**: Downstream services failing

### 5.3 Infrastructure Issues
- **Database Connection Failures**: Unable to connect to vector store
- **Network Partitions**: Services unable to communicate
- **Disk Space Exhaustion**: No space for new data/indices
- **Memory Pressure**: System running out of RAM
- **CPU Saturation**: High CPU usage causing slow responses
- **Service Discovery**: Services unable to find each other

---

## 6. Frontend & User Interface Edge Cases

### 6.1 Chat Interface Failures
- **Message Not Sending**: User messages not reaching backend
- **Duplicate Messages**: Same message sent multiple times
- **Message Ordering**: Messages appearing out of sequence
- **Lost Messages**: Messages disappearing from chat history
- **Scroll Issues**: Chat not auto-scrolling to new messages
- **Input Field Problems**: Text input not accepting user typing

### 6.2 UI State Management
- **Popup Not Opening**: Chat popup failing to display
- **Overlay Issues**: Click-outside-to-close not working
- **Tab Switching Failures**: Problems switching between Chat 1/2/3
- **Responsive Design Breaks**: UI breaking on mobile/tablet
- **Browser Compatibility**: Issues with specific browsers
- **Accessibility Failures**: Screen reader or keyboard navigation issues

### 6.3 User Interaction Edge Cases
- **Rapid Clicking**: User clicking buttons multiple times quickly
- **Network Interruption**: User losing connection mid-conversation
- **Tab Closing**: User closing browser tab during active session
- **Browser Refresh**: User refreshing page during conversation
- **Back Button Navigation**: Using browser back during chat
- **Multiple Windows**: Same user opening chat in multiple tabs

---

## 7. Compliance & Regulatory Edge Cases

### 7.1 Content Compliance Failures
- **Investment Advice Leakage**: System providing recommendations accidentally
- **Performance Comparisons**: Comparing funds against each other
- **Return Calculations**: Calculating or projecting returns
- **Risk Assessments**: Providing risk analysis or ratings
- **Tax Advice**: Giving tax planning suggestions
- **Market Timing**: Suggesting when to buy/sell

### 7.2 Data Privacy Violations
- **PII Collection**: Accidentally collecting personal information
- **Data Retention**: Storing user queries longer than required
- **Data Sharing**: User data exposed to third parties
- **Logging Sensitive Info**: Account numbers or personal details in logs
- **Cross-Border Transfers**: Data moving to non-compliant jurisdictions
- **Right to Erasure**: Failing to delete user data on request

### 7.3 Regulatory Changes
- **SEBI Guideline Updates**: New regulations affecting system behavior
- **AMFI Rule Changes**: Industry body updating requirements
- **Tax Law Changes**: New tax rules affecting fund information
- **Disclosure Requirements**: New mandatory disclosures for funds
- **Reporting Standards**: Changes in how data must be reported
- **Compliance Deadlines**: Time limits for implementing new rules

---

## 8. Performance & Scalability Edge Cases

### 8.1 Load Testing Scenarios
- **Sudden Traffic Spikes**: Massive concurrent user influx
- **Sustained High Load**: Extended periods of high usage
- **Resource Exhaustion**: Memory/CPU/database connections maxed out
- **Slow Response Times**: Responses taking >10 seconds
- **Queue Buildup**: Request queue growing faster than processing
- **Cascading Failures**: One component failure causing system-wide issues

### 8.2 Data Volume Edge Cases
- **Large Corpus Performance**: Degradation with >10,000 documents
- **Frequent Updates**: High frequency data changes affecting performance
- **Complex Queries**: Multi-part queries requiring extensive processing
- **Concurrent Embeddings**: Multiple embedding generations simultaneously
- **Index Rebuilds**: Full reindexing during peak usage
- **Cache Invalidation**: Cache misses causing performance drops

### 8.3 Network & Infrastructure
- **DNS Failures**: Domain resolution problems
- **SSL Certificate Expiry**: HTTPS connections failing
- **CDN Issues**: Content delivery network problems
- **Load Balancer Failures**: Traffic distribution issues
- **Database Locks**: Database operations blocking each other
- **Memory Leaks**: Gradual memory consumption increase

---

## 9. Integration & Third-Party Service Edge Cases

### 9.1 External API Failures
- **Groq API Changes**: Breaking changes to Groq API
- **Pinecone/Vector DB Issues**: Third-party vector store problems
- **GitHub Actions Failures**: CI/CD pipeline failures
- **Webhook Timeouts**: External services not responding
- **API Key Expiration**: Service API keys expiring
- **Service Deprecation**: Third-party services being discontinued

### 9.2 Data Synchronization Issues
- **Stale Data**: Frontend showing outdated information
- **Inconsistent State**: Different parts of system showing different data
- **Replication Lag**: Data not syncing across components
- **Conflict Resolution**: Conflicting updates from different sources
- **Partial Updates**: Some components updated, others not
- **Rollback Failures**: Inability to revert to previous state

### 9.3 Monitoring & Alerting Failures
- **Silent Failures**: Systems failing without alerts
- **False Positives**: Alerts for non-existent problems
- **Alert Fatigue**: Too many alerts causing important ones to be missed
- **Monitoring Gaps**: Critical components not being monitored
- **Delayed Notifications**: Alerts arriving too late to prevent damage
- **Alert Delivery**: Notification systems failing to deliver alerts

---

## 10. Security & Malicious Input Edge Cases

### 10.1 Input Validation Attacks
- **SQL Injection**: Malicious SQL in user queries
- **XSS Attempts**: Script injection in chat messages
- **Command Injection**: System commands in user input
- **Buffer Overflow**: Extremely long input causing memory issues
- **Path Traversal**: Attempts to access unauthorized files
- **LDAP Injection**: Directory service attacks via input

### 10.2 Authentication & Authorization
- **Session Hijacking**: Unauthorized access to user sessions
- **Privilege Escalation**: Users accessing admin functions
- **Token Manipulation**: JWT or session token tampering
- **Brute Force Attacks**: Repeated login attempts
- **Credential Stuffing**: Using leaked credentials
- **Social Engineering**: Attempts to trick system into unauthorized actions

### 10.3 Data Integrity Attacks
- **Man-in-the-Middle**: Intercepting and modifying communications
- **Data Poisoning**: Injecting false information into corpus
- **Replay Attacks**: Reusing valid requests maliciously
- **Race Conditions**: Exploiting timing-based vulnerabilities
- **Denial of Service**: Overwhelming system resources
- **Supply Chain Attacks**: Compromised third-party dependencies

---

## 11. Business Logic & Domain-Specific Edge Cases

### 11.1 Mutual Fund Domain Edge Cases
- **Fund Merger/Acquisition**: Two funds merging, affecting data
- **Fund Name Changes**: Funds rebranding or renaming
- **Scheme Category Changes**: Funds changing investment categories
- **NAV Calculation Changes**: Different NAV calculation methods
- **Exit Load Structure Changes**: Complex exit load scenarios
- **Tax Treatment Changes**: New tax rules affecting fund returns

### 11.2 Regulatory Scenario Edge Cases
- **SEBI Investigation**: Regulatory body investigating specific funds
- **Fund Suspension**: Funds temporarily suspended from trading
- **Category Reclassification**: AMFI reclassifying fund categories
- **Riskometer Changes**: New risk assessment methodologies
- **Disclosure Requirements**: New mandatory disclosure items
- **Investor Protection**: New investor protection rules

### 11.3 Market Condition Edge Cases
- **Market Holidays**: Trading holidays affecting NAV updates
- **Market Crashes**: Extreme market conditions affecting fund data
- **Circuit Breakers**: Market halts affecting real-time data
- **Corporate Actions**: Stock splits, bonuses affecting fund holdings
- **Currency Fluctuations**: Exchange rate effects on international funds
- **Regulatory Changes**: Sudden rule changes affecting operations

---

## 12. Testing & Quality Assurance Edge Cases

### 12.1 Automated Testing Failures
- **Test Data Contamination**: Test data leaking into production
- **Flaky Tests**: Tests passing/failing inconsistently
- **Test Environment Issues**: Test setup not matching production
- **Mock Service Failures**: Test mocks not behaving like real services
- **Coverage Gaps**: Critical code paths not tested
- **Performance Regression**: New code causing performance degradation

### 12.2 User Acceptance Testing
- **User Experience Failures**: System technically working but user-unfriendly
- **Accessibility Issues**: Screen readers, keyboard navigation failing
- **Browser Compatibility**: Issues with specific browser versions
- **Device Compatibility**: Problems on mobile/tablet devices
- **Network Condition Testing**: Failing on slow/unstable networks
- **Language/Localization**: Issues with different languages or regions

### 12.3 Production Monitoring
- **Silent Bugs**: Issues not triggering error alerts
- **Performance Degradation**: Gradual slowdown over time
- **Memory Leaks**: Increasing memory usage over time
- **Data Quality Issues**: Gradual data corruption or inconsistency
- **User Behavior Changes**: Users not adopting new features
- **Business Metric Declines**: KPIs dropping without obvious cause

---

## Evaluation Framework

### Severity Classification
- **Critical**: System completely down, data loss, security breach
- **High**: Major functionality broken, significant user impact
- **Medium**: Partial functionality loss, workaround available
- **Low**: Minor issues, cosmetic problems, edge case scenarios

### Testing Priority
1. **P0**: Critical system failures affecting all users
2. **P1**: High-impact issues affecting core functionality
3. **P2**: Medium-impact issues with workarounds
4. **P3**: Low-impact issues and edge cases

### Success Criteria
- **Edge Case Coverage**: >95% of identified edge cases handled gracefully
- **Graceful Degradation**: System fails safely without data corruption
- **User Communication**: Clear error messages and recovery options
- **Recovery Time**: <5 minutes for non-critical issues
- **Data Integrity**: Zero data loss in any failure scenario

This comprehensive edge case analysis provides a robust framework for evaluating the mutual fund FAQ assistant's reliability, security, and user experience under all possible conditions.
