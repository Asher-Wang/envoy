1.15.1 (Pending)
================
1.15.1 (September 29, 2020)
===========================

Changes
-------
* http: fixed CVE-2020-25017. Previously header matching did not match on all headers for non-inline
  headers. This patch changes the default behavior to always logically match on all headers.
  Multiple individual headers will be logically concatenated with ',' similar to what is done with
  inline headers. This makes the behavior effectively consistent. This behavior can be temporary
  reverted by setting the runtime value `envoy.reloadable_features.header_match_on_all_headers` to
  "false".

  Targeted fixes have been additionally performed on the following extensions which make them
  consider all duplicate headers by default as a comma concatenated list:
    1. Any extension using CEL matching on headers.
    2. The header to metadata filter.
    3. The JWT filter.
    4. The Lua filter.

  Like primary header matching used in routing, RBAC, etc. this behavior can be disabled by setting
  the runtime value `envoy.reloadable_features.header_match_on_all_headers` to false.
* http: the setCopy() header map API previously only set the first header in the case of duplicate
  non-inline headers. setCopy() now behaves similarly to the other set*() APIs and replaces all found
  headers with a single value. This may have had security implications in the extauth filter which
  uses this API. This behavior can be disabled by setting the runtime value
  `envoy.reloadable_features.http_set_copy_replace_all_headers` to false.
1.16.0 (Pending)
================

Incompatible Behavior Changes
-----------------------------
*Changes that are expected to cause an incompatibility if applicable; deployment changes are likely required*

* build: added visibility rules for upstream. If these cause visibility related breakage, see notes in //BUILD.

Minor Behavior Changes
----------------------
*Changes that may cause incompatibilities for some users, but should not for most*

* build: an :ref:`Ubuntu based debug image <install_binaries>` is built and published in DockerHub.
* build: the debug information will be generated separately to reduce target size and reduce compilation time when build in compilation mode `dbg` and `opt`. Users will need to build dwp file to debug with gdb.
* compressor: always insert `Vary` headers for compressible resources even if it's decided not to compress a response due to incompatible `Accept-Encoding` value. The `Vary` header needs to be inserted to let a caching proxy in front of Envoy know that the requested resource still can be served with compression applied.
* decompressor: headers-only requests were incorrectly not advertising accept-encoding when configured to do so. This is now fixed.
* http: added :ref:`contains <envoy_api_msg_type.matcher.StringMatcher>` a new string matcher type which matches if the value of the string has the substring mentioned in contains matcher.
* http: added :ref:`contains <envoy_api_msg_route.HeaderMatcher>` a new header matcher type which matches if the value of the header has the substring mentioned in contains matcher.
* http: added :ref:`headers_to_add <envoy_v3_api_field_extensions.filters.network.http_connection_manager.v3.ResponseMapper.headers_to_add>` to :ref:`local reply mapper <config_http_conn_man_local_reply>` to allow its users to add/append/override response HTTP headers to local replies.
* http: added HCM level configuration of :ref:`error handling on invalid messaging <envoy_v3_api_field_extensions.filters.network.http_connection_manager.v3.HttpConnectionManager.stream_error_on_invalid_http_message>` which substantially changes Envoy's behavior when encountering invalid HTTP/1.1 defaulting to closing the connection instead of allowing reuse. This can temporarily be reverted by setting `envoy.reloadable_features.hcm_stream_error_on_invalid_message` to false, or permanently reverted by setting the HTTP/1 configuration :ref:`override_stream_error_on_invalid_http_message <envoy_v3_api_field_config.core.v3.Http1ProtocolOptions.override_stream_error_on_invalid_http_message>` to true to restore prior HTTP/1.1 behavior (i.e. connection isn't terminated) and to retain prior HTTP/2 behavior (i.e. connection is terminated).
* http: added HCM level configuration of :ref:`error handling on invalid messaging <envoy_v3_api_field_extensions.filters.network.http_connection_manager.v3.HttpConnectionManager.stream_error_on_invalid_http_message>` which substantially changes Envoy's behavior when encountering invalid HTTP/1.1 defaulting to closing the connection instead of allowing reuse. This can temporarily be reverted by setting `envoy.reloadable_features.hcm_stream_error_on_invalid_message` to false, or permanently reverted by setting the :ref:`HCM option <envoy_v3_api_field_extensions.filters.network.http_connection_manager.v3.HttpConnectionManager.stream_error_on_invalid_http_message>` to true to restore prior HTTP/1.1 beavior and setting the *new* HTTP/2 configuration :ref:`override_stream_error_on_invalid_http_message <envoy_v3_api_field_config.core.v3.Http2ProtocolOptions.override_stream_error_on_invalid_http_message>` to false to retain prior HTTP/2 behavior.
* http: changed Envoy to send GOAWAY to HTTP2 downstreams when the :ref:`disable_keepalive <config_overload_manager_overload_actions>` overload action is active. This behavior may be temporarily reverted by setting `envoy.reloadable_features.overload_manager_disable_keepalive_drain_http2` to false.
* http: changed Envoy to send error headers and body when possible. This behavior may be temporarily reverted by setting `envoy.reloadable_features.allow_response_for_timeout` to false.
* http: changed empty trailers encoding behavior by sending empty data with ``end_stream`` true (instead of sending empty trailers) for HTTP/2. This behavior can be reverted temporarily by setting runtime feature ``envoy.reloadable_features.http2_skip_encoding_empty_trailers`` to false.
* http: changed how local replies are processed for requests which transform from grpc to not-grpc, or not-grpc to grpc. Previously the initial generated reply depended on which filter sent the reply, but now the reply is consistently generated the way the downstream expects. This behavior can be temporarily reverted by setting `envoy.reloadable_features.unify_grpc_handling` to false.
* http: clarified and enforced 1xx handling. Multiple 100-continue headers are coalesced when proxying. 1xx headers other than {100, 101} are dropped.
* http: fixed a bug in access logs where early stream termination could be incorrectly tagged as a downstream disconnect, and disconnects after partial response were not flagged.
* http: fixed the 100-continue response path to properly handle upstream failure by sending 5xx responses. This behavior can be temporarily reverted by setting `envoy.reloadable_features.allow_500_after_100` to false.
* http: the per-stream FilterState maintained by the HTTP connection manager will now provide read/write access to the downstream connection FilterState. As such, code that relies on interacting with this might
  see a change in behavior.
* logging: added fine-grain logging for file level log control with logger management at administration interface. It can be enabled by option `--enable-fine-grain-logging`.
* logging: changed default log format to `"[%Y-%m-%d %T.%e][%t][%l][%n] [%g:%#] %v"` and default value of :option:`--log-format-prefix-with-location` to `0`.
* logging: nghttp2 log messages no longer appear at trace level unless `ENVOY_NGHTTP2_TRACE` is set
  in the environment.
* router: added transport failure reason to response body when upstream reset happens. After this change, the response body will be of the form `upstream connect error or disconnect/reset before headers. reset reason:{}, transport failure reason:{}`.This behavior may be reverted by setting runtime feature `envoy.reloadable_features.http_transport_failure_reason_in_body` to false.
* router: now consumes all retry related headers to prevent them from being propagated to the upstream. This behavior may be reverted by setting runtime feature `envoy.reloadable_features.consume_all_retry_headers` to false.
* thrift_proxy: special characters {'\0', '\r', '\n'} will be stripped from thrift headers.

Bug Fixes
---------
*Changes expected to improve the state of the world and are unlikely to have negative effects*

* csrf: fixed issues with regards to origin and host header parsing.
* dynamic_forward_proxy: only perform DNS lookups for routes to Dynamic Forward Proxy clusters since other cluster types handle DNS lookup themselves.
* fault: fixed an issue with `active_faults` gauge not being decremented for when abort faults were injected.
* fault: made the HeaderNameValues::prefix() method const.
* grpc-web: fixed an issue with failing HTTP/2 requests on some browsers. Notably, WebKit-based browsers (https://bugs.webkit.org/show_bug.cgi?id=210108), Internet Explorer 11, and Edge (pre-Chromium).
* http: made the HeaderValues::prefix() method const.
* jwt_authn: supports jwt payload without "iss" field.
* listener: fixed crash at listener inplace update when connetion load balancer is set.
* rocketmq_proxy network-level filter: fixed an issue involving incorrect header lengths. In debug mode it causes crash and in release mode it causes underflow.
* thrift_proxy: fixed crashing bug on request overflow.
* udp_proxy: fixed a crash due to UDP packets being processed after listener removal.

Removed Config or Runtime
-------------------------
*Normally occurs at the end of the* :ref:`deprecation period <deprecated>`

* http: removed legacy header sanitization and the runtime guard `envoy.reloadable_features.strict_header_validation`.
* http: removed legacy transfer-encoding enforcement and runtime guard `envoy.reloadable_features.reject_unsupported_transfer_encodings`.
* http: removed configurable strict host validation and runtime guard `envoy.reloadable_features.strict_authority_validation`.
* http: removed the connection header sanitization runtime guard `envoy.reloadable_features.connection_header_sanitization`.

New Features
------------
* access log: added a :ref:`dynamic metadata filter<envoy_v3_api_msg_config.accesslog.v3.MetadataFilter>` for access logs, which filters whether to log based on matching dynamic metadata.
* access log: added support for :ref:`%DOWNSTREAM_PEER_FINGERPRINT_1% <config_access_log_format_response_flags>` as a response flag.
* access log: added support for nested objects in :ref:`JSON logging mode <config_access_log_format_dictionaries>`.
* access log: added :ref:`omit_empty_values<envoy_v3_api_field_config.core.v3.SubstitutionFormatString.omit_empty_values>` option to omit unset value from formatted log.
* admin: added the ability to dump init manager unready targets information :ref:`/init_dump <operations_admin_interface_init_dump>` and :ref:`/init_dump?mask={} <operations_admin_interface_init_dump_by_mask>`.
* build: enable building envoy :ref:`arm64 images <arm_binaries>` by buildx tool in x86 CI platform.
* cluster: added new :ref:`connection_pool_per_downstream_connection <envoy_v3_api_field_config.cluster.v3.Cluster.connection_pool_per_downstream_connection>` flag, which enable creation of a new connection pool for each downstream connection.
* decompressor filter: reports compressed and uncompressed bytes in trailers.
* dns_filter: added support for answering :ref:`service record<envoy_v3_api_msg_data.dns.v3.DnsTable.DnsService>` queries.
* dynamic_forward_proxy: added :ref:`use_tcp_for_dns_lookups<envoy_v3_api_field_extensions.common.dynamic_forward_proxy.v3.DnsCacheConfig.use_tcp_for_dns_lookups>` option to use TCP for DNS lookups in order to match the DNS options for :ref:`Clusters<envoy_v3_api_msg_config.cluster.v3.Cluster>`.
* ext_authz filter: added support for emitting dynamic metadata for both :ref:`HTTP <config_http_filters_ext_authz_dynamic_metadata>` and :ref:`network <config_network_filters_ext_authz_dynamic_metadata>` filters.
  The emitted dynamic metadata is set by :ref:`dynamic metadata <envoy_v3_api_field_service.auth.v3.CheckResponse.dynamic_metadata>` field in a returned :ref:`CheckResponse <envoy_v3_api_msg_service.auth.v3.CheckResponse>`.
* grpc-json: support specifying `response_body` field in for `google.api.HttpBody` message.
* hds: added :ref:`cluster_endpoints_health <envoy_v3_api_field_service.health.v3.EndpointHealthResponse.cluster_endpoints_health>` to HDS responses, keeping endpoints in the same groupings as they were configured in the HDS specifier by cluster and locality instead of as a flat list.
* hds: added :ref:`transport_socket_matches <envoy_v3_api_field_service.health.v3.ClusterHealthCheck.transport_socket_matches>` to HDS cluster health check specifier, so the existing match filter :ref:`transport_socket_match_criteria <envoy_v3_api_field_config.core.v3.HealthCheck.transport_socket_match_criteria>` in the repeated field :ref:`health_checks <envoy_v3_api_field_service.health.v3.ClusterHealthCheck.health_checks>` has context to match against. This unblocks support for health checks over HTTPS and HTTP/2.
* http: added support for :ref:`%DOWNSTREAM_PEER_FINGERPRINT_1% <config_http_conn_man_headers_custom_request_headers>` as custom header.
* http: added :ref:`allow_chunked_length <envoy_v3_api_field_config.core.v3.Http1ProtocolOptions.allow_chunked_length>` configuration option for HTTP/1 codec to allow processing requests/responses with both Content-Length and Transfer-Encoding: chunked headers. If such message is served and option is enabled - per RFC Content-Length is ignored and removed.
* http: introduced new HTTP/1 and HTTP/2 codec implementations that will remove the use of exceptions for control flow due to high risk factors and instead use error statuses. The old behavior is used by default, but the new codecs can be enabled for testing by setting the runtime feature `envoy.reloadable_features.new_codec_behavior` to true. The new codecs will be in development for one month, and then enabled by default while the old codecs are deprecated.
* load balancer: added :ref:`RingHashLbConfig<envoy_v3_api_msg_config.cluster.v3.Cluster.MaglevLbConfig>` to configure the table size of Maglev consistent hash.
* load balancer: added a :ref:`configuration<envoy_v3_api_msg_config.cluster.v3.Cluster.LeastRequestLbConfig>` option to specify the active request bias used by the least request load balancer.
* load balancer: added an :ref:`option <envoy_v3_api_field_config.cluster.v3.Cluster.LbSubsetConfig.LbSubsetSelector.single_host_per_subset>` to optimize subset load balancing when there is only one host per subset.
* load balancer: added support for bounded load per host for consistent hash load balancers via :ref:`hash_balance_factor <envoy_api_field_Cluster.CommonLbConfig.consistent_hashing_lb_config>`.
* local_reply config: added :ref:`content_type<envoy_v3_api_field_config.core.v3.SubstitutionFormatString.content_type>` field to set content-type.
* lua: added Lua APIs to access :ref:`SSL connection info <config_http_filters_lua_ssl_socket_info>` object.
* lua: added Lua API for :ref:`base64 escaping a string <config_http_filters_lua_stream_handle_api_base64_escape>`.
* lua: added new :ref:`source_code <envoy_v3_api_field_extensions.filters.http.lua.v3.LuaPerRoute.source_code>` field to support the dispatching of inline Lua code in per route configuration of Lua filter.
* overload management: add :ref:`scaling <envoy_v3_api_field_config.overload.v3.Trigger.scaled>` trigger for OverloadManager actions.
* postgres network filter: :ref:`metadata <config_network_filters_postgres_proxy_dynamic_metadata>` is produced based on SQL query.
* ratelimit: added :ref:`enable_x_ratelimit_headers <envoy_v3_api_msg_extensions.filters.http.ratelimit.v3.RateLimit>` option to enable `X-RateLimit-*` headers as defined in `draft RFC <https://tools.ietf.org/id/draft-polli-ratelimit-headers-03.html>`_.
* ratelimit: added :ref:`per route config <envoy_v3_api_msg_extensions.filters.http.ratelimit.v3.RateLimitPerRoute>` for rate limit filter.
* ratelimit: added support for optional :ref:`descriptor_key <envoy_v3_api_field_config.route.v3.RateLimit.Action.generic_key>` to Generic Key action.
* rbac filter: added a log action to the :ref:`RBAC filter <envoy_v3_api_msg_config.rbac.v3.RBAC>` which sets dynamic metadata to inform access loggers whether to log.
* redis: added fault injection support :ref:`fault injection for redis proxy <envoy_v3_api_field_extensions.filters.network.redis_proxy.v3.RedisProxy.faults>`, described further in :ref:`configuration documentation <config_network_filters_redis_proxy>`.
* router: added a new :ref:`rate limited retry back off <envoy_v3_api_msg_config.route.v3.RetryPolicy.RateLimitedRetryBackOff>` strategy that uses headers like `Retry-After` or `X-RateLimit-Reset` to decide the back off interval.
* router: added new
  :ref:`envoy-ratelimited<config_http_filters_router_retry_policy-envoy-ratelimited>`
  retry policy, which allows retrying envoy's own rate limited responses.
* router: added new :ref:`host_rewrite_path_regex <envoy_v3_api_field_config.route.v3.RouteAction.host_rewrite_path_regex>`
  option, which allows rewriting Host header based on path.
* router: added support for DYNAMIC_METADATA :ref:`header formatter <config_http_conn_man_headers_custom_request_headers>`.
* router_check_tool: added support for `request_header_matches`, `response_header_matches` to :ref:`router check tool <config_tools_router_check_tool>`.
* signal: added support for calling fatal error handlers without envoy's signal handler, via FatalErrorHandler::callFatalErrorHandlers().
* stats: added optional histograms to :ref:`cluster stats <config_cluster_manager_cluster_stats_request_response_sizes>`
  that track headers and body sizes of requests and responses.
* stats: allow configuring histogram buckets for stats sinks and admin endpoints that support it.
* tap: added :ref:`generic body matcher<envoy_v3_api_msg_config.tap.v3.HttpGenericBodyMatch>` to scan http requests and responses for text or hex patterns.
* tcp_proxy: allow earlier network filters to set metadataMatchCriteria on the connection StreamInfo to influence load balancing.
* tls: introduce new :ref:`extension point<envoy_v3_api_field_extensions.transport_sockets.tls.v3.CommonTlsContext.custom_handshaker>` for overriding :ref:`TLS handshaker <arch_overview_ssl>` behavior.
* tls: switched from using socket BIOs to using custom BIOs that know how to interact with IoHandles. The feature can be disabled by setting runtime feature `envoy.reloadable_features.tls_use_io_handle_bio` to false.
* tracing: added ability to set some :ref:`optional segment fields<envoy_v3_api_field_config.trace.v3.XRayConfig.segment_fields>` in the AWS  X-Ray tracer.
* udp_proxy: added :ref:`hash_policies <envoy_v3_api_msg_extensions.filters.udp.udp_proxy.v3.UdpProxyConfig>` to support hash based routing.
* udp_proxy: added :ref:`use_original_src_ip <envoy_v3_api_msg_extensions.filters.udp.udp_proxy.v3.UdpProxyConfig>` option to replicate the downstream remote address of the packets on the upstream side of Envoy. It is similar to :ref:`original source filter <envoy_v3_api_msg_extensions.filters.listener.original_src.v3.OriginalSrc>`.
* watchdog: support randomizing the watchdog's kill timeout to prevent synchronized kills via a maximium jitter parameter :ref:`max_kill_timeout_jitter<envoy_v3_api_field_config.bootstrap.v3.Watchdog.max_kill_timeout_jitter>`.
* watchdog: supports an extension point where actions can be registered to fire on watchdog events such as miss, megamiss, kill and multikill. See ref:`watchdog actions<envoy_v3_api_field_config.bootstrap.v3.Watchdog.actions>`.
* watchdog: watchdog action extension that does cpu profiling. See ref:`Profile Action <envoy_v3_api_file_envoy/extensions/watchdog/profile_action/v3alpha/profile_action.proto>`.
* watchdog: watchdog action extension that sends SIGABRT to the stuck thread to terminate the process. See ref:`Abort Action <envoy_v3_api_file_envoy/extensions/watchdog/abort_action/v3alpha/abort_action.proto>`.
* xds: added :ref:`extension config discovery<envoy_v3_api_msg_config.core.v3.ExtensionConfigSource>` support for HTTP filters.
* zlib: added option to use `zlib-ng <https://github.com/zlib-ng/zlib-ng>`_ as zlib library.
* access log: added the :ref:`formatters <envoy_v3_api_field_config.core.v3.SubstitutionFormatString.formatters>` extension point for custom formatters (command operators).
* access log: support command operator: %REQUEST_HEADERS_BYTES%, %RESPONSE_HEADERS_BYTES%, and %RESPONSE_TRAILERS_BYTES%.
* compression: add brotli :ref:`compressor <envoy_v3_api_msg_extensions.compression.brotli.compressor.v3.Brotli>` and :ref:`decompressor <envoy_v3_api_msg_extensions.compression.brotli.decompressor.v3.Brotli>`.
* config: add `envoy.features.fail_on_any_deprecated_feature` runtime key, which matches the behaviour of compile-time flag `ENVOY_DISABLE_DEPRECATED_FEATURES`, i.e. use of deprecated fields will cause a crash.
* dispatcher: supports a stack of `Envoy::ScopeTrackedObject` instead of a single tracked object. This will allow Envoy to dump more debug information on crash.
* ext_authz: added :ref:`response_headers_to_add <envoy_v3_api_field_service.auth.v3.OkHttpResponse.response_headers_to_add>` to support sending response headers to downstream clients on OK authorization checks via gRPC.
* ext_authz: added :ref:`allowed_client_headers_on_success <envoy_v3_api_field_extensions.filters.http.ext_authz.v3.AuthorizationResponse.allowed_client_headers_on_success>` to support sending response headers to downstream clients on OK external authorization checks via HTTP.
* grpc_json_transcoder: added option :ref:`strict_http_request_validation <envoy_v3_api_field_extensions.filters.http.grpc_json_transcoder.v3.GrpcJsonTranscoder.strict_http_request_validation>` to reject invalid requests early.
* grpc_json_transcoder: filter can now be configured on per-route/per-vhost level as well. Leaving empty list of services in the filter configuration disables transcoding on the specific route.
* http: added support for `Envoy::ScopeTrackedObject` for HTTP/1 dispatching. Crashes while inside the dispatching loop should dump debug information.
* http: added support for :ref:`preconnecting <envoy_v3_api_msg_config.cluster.v3.Cluster.PreconnectPolicy>`. Preconnecting is off by default, but recommended for clusters serving latency-sensitive traffic, especially if using HTTP/1.1.
* http: change frame flood and abuse checks to the upstream HTTP/2 codec to ON by default. It can be disabled by setting the `envoy.reloadable_features.upstream_http2_flood_checks` runtime key to false.
* overload: add support for scaling :ref:`transport connection timeouts<envoy_v3_api_enum_value_config.overload.v3.ScaleTimersOverloadActionConfig.TimerType.TRANSPORT_SOCKET_CONNECT>`. This can be used to reduce the TLS handshake timeout in response to overload.
* postgres: added ability to :ref:`terminate SSL<envoy_v3_api_field_extensions.filters.network.postgres_proxy.v3alpha.PostgresProxy.terminate_ssl>`.
* route config: added :ref:`allow_post field <envoy_v3_api_field_config.route.v3.RouteAction.UpgradeConfig.ConnectConfig.allow_post>` for allowing POST payload as raw TCP.
* route config: added :ref:`max_direct_response_body_size_bytes <envoy_v3_api_field_config.route.v3.RouteConfiguration.max_direct_response_body_size_bytes>` to set maximum :ref:`direct response body <envoy_v3_api_field_config.route.v3.DirectResponseAction.body>` size in bytes. If not specified the default remains 4096 bytes.
* server: added *fips_mode* to :ref:`server compilation settings <server_compilation_settings_statistics>` related statistic.
* tcp_proxy: add support for converting raw TCP streams into HTTP/1.1 CONNECT requests. See :ref:`upgrade documentation <tunneling-tcp-over-http>` for details.
* tcp_proxy: added a :ref:`use_post field <envoy_v3_api_field_extensions.filters.network.tcp_proxy.v3.TcpProxy.TunnelingConfig.use_post>` for using HTTP POST to proxy TCP streams.
* tcp_proxy: added a :ref:`headers_to_add field <envoy_v3_api_field_extensions.filters.network.tcp_proxy.v3.TcpProxy.TunnelingConfig.headers_to_add>` for setting additional headers to the HTTP requests for TCP proxing.

Deprecated
----------

* build: Alpine based debug image is deprecated in favor of :ref:`Ubuntu based debug image <install_binaries>`.
* The :ref:`track_timeout_budgets <envoy_v3_api_field_config.cluster.v3.Cluster.track_timeout_budgets>`
  field has been deprecated in favor of `timeout_budgets` part of an :ref:`Optional Configuration <envoy_v3_api_field_config.cluster.v3.Cluster.track_cluster_stats>`.
* hds: the :ref:`endpoints_health <envoy_v3_api_field_service.health.v3.EndpointHealthResponse.endpoints_health>`
  field has been deprecated in favor of :ref:`cluster_endpoints_health <envoy_v3_api_field_service.health.v3.EndpointHealthResponse.cluster_endpoints_health>` to maintain
  grouping by cluster and locality.
* router: the :ref:`include_vh_rate_limits <envoy_v3_api_field_config.route.v3.RouteAction.include_vh_rate_limits>` field has been deprecated in favor of :ref:`vh_rate_limits <envoy_v3_api_field_extensions.filters.http.ratelimit.v3.RateLimitPerRoute.vh_rate_limits>`.
* tap: the :ref:`match_config <envoy_v3_api_field_config.tap.v3.TapConfig.match_config>` field has been deprecated in favor of
  :ref:`match <envoy_v3_api_field_config.tap.v3.TapConfig.match>` field.
* ext_authz: the :ref:`dynamic metadata <envoy_v3_api_field_service.auth.v3.OkHttpResponse.dynamic_metadata>` field in :ref:`OkHttpResponse <envoy_v3_api_msg_service.auth.v3.OkHttpResponse>`
  has been deprecated in favor of :ref:`dynamic metadata <envoy_v3_api_field_service.auth.v3.CheckResponse.dynamic_metadata>` field in :ref:`CheckResponse <envoy_v3_api_msg_service.auth.v3.CheckResponse>`.
* router_check_tool: `request_header_fields`, `response_header_fields` config deprecated in favor of `request_header_matches`, `response_header_matches`.
