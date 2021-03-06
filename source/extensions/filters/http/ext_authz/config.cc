#include "extensions/filters/http/ext_authz/config.h"

#include <chrono>
#include <string>

#include "envoy/config/core/v3/grpc_service.pb.h"
#include "envoy/extensions/filters/http/ext_authz/v3/ext_authz.pb.h"
#include "envoy/extensions/filters/http/ext_authz/v3/ext_authz.pb.validate.h"
#include "envoy/registry/registry.h"

#include "common/protobuf/utility.h"

#include "extensions/filters/common/ext_authz/ext_authz_grpc_impl.h"
#include "extensions/filters/common/ext_authz/ext_authz_http_impl.h"
#include "extensions/filters/http/ext_authz/ext_authz.h"

namespace Envoy {
namespace Extensions {
namespace HttpFilters {
namespace ExtAuthz {

Http::FilterFactoryCb ExtAuthzFilterConfig::createFilterFactoryFromProtoTyped(
    const envoy::extensions::filters::http::ext_authz::v3::ExtAuthz& proto_config,
    const std::string& stats_prefix, Server::Configuration::FactoryContext& context) {
  const auto filter_config =
      std::make_shared<FilterConfig>(proto_config, context.localInfo(), context.scope(),
                                     context.runtime(), context.httpContext(), stats_prefix);
  Http::FilterFactoryCb callback;

  if (proto_config.has_http_service()) {
    // Raw HTTP client.
    const uint32_t timeout_ms = PROTOBUF_GET_MS_OR_DEFAULT(proto_config.http_service().server_uri(),
                                                           timeout, DefaultTimeout);
    const auto client_config =
        std::make_shared<Extensions::Filters::Common::ExtAuthz::ClientConfig>(
            proto_config, timeout_ms, proto_config.http_service().path_prefix());
    callback = [filter_config, client_config,
                &context](Http::FilterChainFactoryCallbacks& callbacks) {
      auto client = std::make_unique<Extensions::Filters::Common::ExtAuthz::RawHttpClientImpl>(
          context.clusterManager(), client_config);
      callbacks.addStreamFilter(std::make_shared<Filter>(filter_config, std::move(client)));
    };
  } else if (proto_config.grpc_service().has_google_grpc()) {
    // Google gRPC client.

    // The use_alpha field was there select the v2alpha api version, which is
    // long deprecated and should not be used anymore.
    if (proto_config.hidden_envoy_deprecated_use_alpha()) {
      throw EnvoyException("The use_alpha field is deprecated and is no longer supported.");
    }

    const uint32_t timeout_ms =
        PROTOBUF_GET_MS_OR_DEFAULT(proto_config.grpc_service(), timeout, DefaultTimeout);
    Grpc::AsyncClientCacheSingletonSharedPtr async_client_cache_singleton =
        Grpc::getAsyncClientCacheSingleton(context.getServerFactoryContext());
    Grpc::AsyncClientCacheSharedPtr async_client_cache =
        async_client_cache_singleton->getOrCreateAsyncClientCache(
            context.clusterManager().grpcAsyncClientManager(), context.scope(),
            context.threadLocal(), proto_config.grpc_service());
    callback = [async_client_cache, filter_config, timeout_ms, proto_config,
                transport_api_version = Config::Utility::getAndCheckTransportVersion(proto_config)](
                   Http::FilterChainFactoryCallbacks& callbacks) {
      auto client = std::make_unique<Filters::Common::ExtAuthz::GrpcClientImpl>(
          async_client_cache->getAsyncClient(), std::chrono::milliseconds(timeout_ms),
          transport_api_version);
      callbacks.addStreamFilter(std::make_shared<Filter>(filter_config, std::move(client)));
    };
  } else {
    // gRPC client.
    const uint32_t timeout_ms =
        PROTOBUF_GET_MS_OR_DEFAULT(proto_config.grpc_service(), timeout, DefaultTimeout);
    callback = [grpc_service = proto_config.grpc_service(), &context, filter_config, timeout_ms,
                transport_api_version = proto_config.transport_api_version(),
                use_alpha = proto_config.hidden_envoy_deprecated_use_alpha()](
                   Http::FilterChainFactoryCallbacks& callbacks) {
      const auto async_client_factory =
          context.clusterManager().grpcAsyncClientManager().factoryForGrpcService(
              grpc_service, context.scope(), true);
      auto client = std::make_unique<Filters::Common::ExtAuthz::GrpcClientImpl>(
          async_client_factory->create(), std::chrono::milliseconds(timeout_ms),
          transport_api_version);
      callbacks.addStreamFilter(std::make_shared<Filter>(filter_config, std::move(client)));
    };
  }

  return callback;
};

Router::RouteSpecificFilterConfigConstSharedPtr
ExtAuthzFilterConfig::createRouteSpecificFilterConfigTyped(
    const envoy::extensions::filters::http::ext_authz::v3::ExtAuthzPerRoute& proto_config,
    Server::Configuration::ServerFactoryContext&, ProtobufMessage::ValidationVisitor&) {
  return std::make_shared<FilterConfigPerRoute>(proto_config);
}

/**
 * Static registration for the external authorization filter. @see RegisterFactory.
 */
REGISTER_FACTORY(ExtAuthzFilterConfig,
                 Server::Configuration::NamedHttpFilterConfigFactory){"envoy.ext_authz"};

} // namespace ExtAuthz
} // namespace HttpFilters
} // namespace Extensions
} // namespace Envoy
