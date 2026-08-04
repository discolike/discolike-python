from __future__ import annotations

import typer

from discolike_cli._output import emit
from discolike_cli._output import handle_errors

FORMAT_HELP = "Output format: json or table (table auto-selected on a TTY; falls back to JSON for non-tabular data)."

search_providers_app = typer.Typer(help="Manage BYOK web search provider integrations (Tavily, Serper, etc.).")
llm_providers_app = typer.Typer(help="Manage BYOK LLM provider integrations (OpenAI, Anthropic, custom endpoints).")


@search_providers_app.command("list")
@handle_errors
def search_list_command(
    ctx: typer.Context,
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """List search provider integrations for the organization."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).search_providers.list(), fmt=fmt)


@search_providers_app.command("create")
@handle_errors
def search_create_command(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="User-friendly name for the integration."),
    provider: str = typer.Option(..., "--provider", help="Search provider key, e.g. tavily or serper."),
    search_model: str = typer.Option(..., "--search-model", help="Search model key, e.g. tavily/search."),
    api_key: str | None = typer.Option(None, "--api-key", help="Provider API key (omit for free providers)."),
    base_url: str | None = typer.Option(None, "--base-url", help="Custom endpoint URL for a LiteLLM proxy."),
) -> None:
    """Create a search provider integration (connectivity is validated first)."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).search_providers.create(
            integration_name=name,
            provider=provider,
            search_model=search_model,
            api_key=api_key,
            base_url=base_url,
        )
    )


@search_providers_app.command("update")
@handle_errors
def search_update_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the search provider integration to update."),
    name: str = typer.Option(..., "--name", help="User-friendly name for the integration."),
    provider: str = typer.Option(..., "--provider", help="Search provider key, e.g. tavily or serper."),
    search_model: str = typer.Option(..., "--search-model", help="Search model key, e.g. tavily/search."),
    api_key: str | None = typer.Option(None, "--api-key", help="New provider API key (omit to keep the stored key)."),
    base_url: str | None = typer.Option(None, "--base-url", help="Custom endpoint URL for a LiteLLM proxy."),
) -> None:
    """Update a search provider integration."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).search_providers.update(
            integration_id=integration_id,
            integration_name=name,
            provider=provider,
            search_model=search_model,
            api_key=api_key,
            base_url=base_url,
        )
    )


@search_providers_app.command("delete")
@handle_errors
def search_delete_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the search provider integration to delete."),
) -> None:
    """Delete a search provider integration (admin only)."""
    from discolike_cli.main import get_client

    get_client(ctx).search_providers.delete(integration_id=integration_id)
    emit({"deleted": integration_id})


@search_providers_app.command("set-default")
@handle_errors
def search_set_default_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the integration to make the organization default."),
) -> None:
    """Set a search provider integration as the organization default (admin only)."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).search_providers.set_default(integration_id=integration_id))


@search_providers_app.command("clear-default")
@handle_errors
def search_clear_default_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the integration currently set as default."),
) -> None:
    """Remove the default flag from a search provider integration (admin only)."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).search_providers.clear_default(integration_id=integration_id))


@search_providers_app.command("models")
@handle_errors
def search_models_command(
    ctx: typer.Context,
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """List available search models grouped by provider, with cost per query."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).search_providers.models(), fmt=fmt)


@llm_providers_app.command("list")
@handle_errors
def llm_list_command(
    ctx: typer.Context,
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """List LLM provider integrations for the organization."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).llm_providers.list(), fmt=fmt)


@llm_providers_app.command("create")
@handle_errors
def llm_create_command(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", help="User-friendly name for the integration."),
    provider: str = typer.Option(..., "--provider", help="LLM provider name: openai, anthropic, or custom."),
    api_key: str = typer.Option(..., "--api-key", help="API key for the provider."),
    model_name: str = typer.Option(..., "--model-name", help="Default model name for this integration."),
    base_url: str | None = typer.Option(None, "--base-url", help="Endpoint URL (required for the custom provider)."),
) -> None:
    """Create an LLM provider integration."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).llm_providers.create(
            integration_name=name,
            provider=provider,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
        )
    )


@llm_providers_app.command("get")
@handle_errors
def llm_get_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the LLM provider integration to fetch."),
    fmt: str | None = typer.Option(None, "--format", help=FORMAT_HELP),
) -> None:
    """Get a single LLM provider integration by ID."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).llm_providers.get(integration_id=integration_id), fmt=fmt)


@llm_providers_app.command("update")
@handle_errors
def llm_update_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the LLM provider integration to update."),
    name: str = typer.Option(..., "--name", help="User-friendly name for the integration."),
    provider: str = typer.Option(..., "--provider", help="LLM provider name: openai, anthropic, or custom."),
    model_name: str = typer.Option(..., "--model-name", help="Default model name for this integration."),
    api_key: str | None = typer.Option(None, "--api-key", help="New API key (omit to keep the stored key)."),
    base_url: str | None = typer.Option(None, "--base-url", help="Endpoint URL (required for the custom provider)."),
) -> None:
    """Update an LLM provider integration."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).llm_providers.update(
            integration_id=integration_id,
            integration_name=name,
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
        )
    )


@llm_providers_app.command("delete")
@handle_errors
def llm_delete_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the LLM provider integration to delete."),
) -> None:
    """Delete an LLM provider integration (admin only)."""
    from discolike_cli.main import get_client

    get_client(ctx).llm_providers.delete(integration_id=integration_id)
    emit({"deleted": integration_id})


@llm_providers_app.command("set-default")
@handle_errors
def llm_set_default_command(
    ctx: typer.Context,
    integration_id: str = typer.Argument(..., help="ID of the integration to make the organization default."),
) -> None:
    """Set an LLM provider integration as the organization default (admin only)."""
    from discolike_cli.main import get_client

    emit(get_client(ctx).llm_providers.set_default(integration_id=integration_id))


@llm_providers_app.command("test-connection")
@handle_errors
def llm_test_connection_command(
    ctx: typer.Context,
    name: str = typer.Option("cli-test", "--name", help="Name to label the test configuration."),
    provider: str = typer.Option(..., "--provider", help="LLM provider name: openai, anthropic, or custom."),
    api_key: str = typer.Option(..., "--api-key", help="API key for the provider."),
    model_name: str = typer.Option(..., "--model-name", help="Model name to test against."),
    base_url: str | None = typer.Option(None, "--base-url", help="Endpoint URL (required for the custom provider)."),
) -> None:
    """Test a provider configuration before saving it."""
    from discolike_cli.main import get_client

    emit(
        get_client(ctx).llm_providers.test_connection(
            integration_name=name,
            provider=provider,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
        )
    )
