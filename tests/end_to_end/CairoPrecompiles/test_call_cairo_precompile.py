import pytest
import pytest_asyncio
from eth_abi import encode

from kakarot_scripts.utils.kakarot import deploy, eth_send_transaction
from kakarot_scripts.utils.starknet import get_contract, invoke
from tests.utils.errors import cairo_error

CALL_CAIRO_PRECOMPILE = 0x75004


@pytest_asyncio.fixture(scope="module")
async def cairo_counter(max_fee, deployer):
    cairo_counter = get_contract("Counter", provider=deployer)

    yield cairo_counter

    await invoke("Counter", "set_counter", 0)


@pytest_asyncio.fixture(scope="module")
async def cairo_counter_caller(cairo_counter):
    return await deploy(
        "CairoPrecompiles",
        "CallCairoPrecompileTest",
        cairo_counter.address,
    )


@pytest.mark.asyncio(scope="module")
@pytest.mark.CairoPrecompiles
class TestCairoPrecompiles:
    class TestCounterPrecompiles:
        async def test_should_increase_counter(self, cairo_counter, owner):
            prev_count = (await cairo_counter.functions["get"].call()).count

            call = cairo_counter.functions["inc"].prepare_call()
            tx_data = encode(
                ["uint256", "uint256", "uint256[]"],
                [int(call.to_addr), int(call.selector), call.calldata],
            )

            await eth_send_transaction(
                to=f"0x{CALL_CAIRO_PRECOMPILE:040x}",
                gas=41000,
                data=tx_data,
                value=0,
                caller_eoa=owner.starknet_contract,
            )

            new_count = (await cairo_counter.functions["get"].call()).count
            expected_count = prev_count + 1
            assert new_count == expected_count

        async def test_should_increase_counter_from_solidity(
            self, cairo_counter, cairo_counter_caller
        ):
            prev_count = (await cairo_counter.functions["get"].call()).count
            await cairo_counter_caller.incrementCairoCounter()
            new_count = (await cairo_counter.functions["get"].call()).count
            expected_increment = 1
            assert new_count == prev_count + expected_increment

        async def test_should_fail_when_called_with_delegatecall(
            self, cairo_counter_caller
        ):
            with cairo_error(
                "EVM tx reverted, reverting SN tx because of previous calls to cairo precompiles"
            ):
                await cairo_counter_caller.incrementCairoCounterDelegatecall()

        async def test_should_fail_when_called_with_callcode(
            self, cairo_counter_caller
        ):
            with cairo_error(
                "EVM tx reverted, reverting SN tx because of previous calls to cairo precompiles"
            ):
                await cairo_counter_caller.incrementCairoCounterCallcode()
