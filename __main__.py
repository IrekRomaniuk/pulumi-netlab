"""
An Azure Python Pulumi program: create networks with subnets, routes and virtual gateways
https://github.com/pulumi/pulumi-azure/issues/551
"""

import pulumi
import pulumi_azure as azure

env = pulumi.get_stack()
project = pulumi.get_project()
config = pulumi.Config()
vnets = config.require_object('vnets')
data = config.require_object('data')
vm = config.require_object('vm')
rg_name = data['rg_prefix']+project+env
peerings = config.require_object('peerings')
rg = azure.core.ResourceGroup(rg_name, name=rg_name)
subscriptionId=pulumi.Config("azure").get("subscriptionId")
virtual_network_id, nic_ip, public_address_id, virtual_network_gateways_id = {}, {}, {}, {} 
for vnet in vnets:
    for vnet_name, vnet_dict in vnet.items():
        # print (vnet_name, vnet_dict['addr'],vnet_dict['subnets'],vnet_dict['bgp_settings'])
        virtual_network=azure.network.VirtualNetwork(vnet_name, name=vnet_name, resource_group_name=rg.name,
                address_spaces=vnet_dict['addr'], subnets=vnet_dict['subnets'], location=rg.location)
        virtual_network_id[vnet_name]=virtual_network.id 
        for subnet in vnet_dict['subnets']:
            if subnet['name'] == 'GatewaySubnet' and not data['skip_gateways']:
                public_gw_ip = azure.network.PublicIp("PIP-GW-" + vnet_name, # name = public_address,
                resource_group_name=rg.name, location=rg.location, allocation_method="Dynamic")              
                subnet_id = '/subscriptions/' + subscriptionId + '/resourceGroups/' + rg_name + '/providers/Microsoft.Network/virtualNetworks/' + vnet_name + '/subnets/GatewaySubnet'
                # subnet_gw = azure.network.get_subnet(name="GatewaySubnet", virtual_network_name=vnet_name, resource_group_name=rg.name)
                ip_configurations = [{"public_ip_address_id" : public_gw_ip.id, "subnet_id": subnet_id}]
                virtual_network_gateways=azure.network.VirtualNetworkGateway("GW-"+ vnet_name, name="GW-"+ vnet_name, resource_group_name=rg.name,
                enable_bgp=True, bgp_settings = vnet_dict['bgp_settings'],ip_configurations=ip_configurations, sku="VpnGw1", type="Vpn", 
                opts=pulumi.ResourceOptions(depends_on=[virtual_network], custom_timeouts=pulumi.CustomTimeouts(create='10m'))) 
                public_address_id["PIP-GW-" + vnet_name]=public_gw_ip.id
                virtual_network_gateways_id[vnet_name]=virtual_network_gateways.id
            if subnet['name'] == 'AzureBastionSubnet':
                public_bh_ip = azure.network.PublicIp("PIP-BH-" + vnet_name, resource_group_name=rg.name, location=rg.location, 
                sku="Standard", allocation_method="Static")   
                subnet_id = '/subscriptions/' + subscriptionId + '/resourceGroups/' + rg_name + '/providers/Microsoft.Network/virtualNetworks/' + vnet_name+ '/subnets/AzureBastionSubnet'
                # subnet_bh = azure.network.get_subnet(name="AzureBastionSubnet", virtual_network_name=vnet_name, resource_group_name=rg.name)
                bastion_host= azure.compute.BastionHost("BH-"+vnet_name, name="BH-"+vnet_name, resource_group_name=rg.name,
                ip_configuration={ "name": "ip-configuration", "subnet_id": subnet_id, "public_ip_address_id": public_bh_ip.id },
                opts=pulumi.ResourceOptions(depends_on=[virtual_network]))
                public_address_id["PIP-BH-" + vnet_name] = public_bh_ip.id
            if subnet['name'] == 'TestSubnet':  
                subnet_id = '/subscriptions/' + subscriptionId + '/resourceGroups/' + rg_name + '/providers/Microsoft.Network/virtualNetworks/' + vnet_name + '/subnets/TestSubnet'
                # subnet_tv = azure.network.get_subnet(name="TestSubnet", virtual_network_name=vnet_name, resource_group_name=rg.name)
                ip_configurations= [{ "name": "ip-cfg", "subnet_id": subnet_id, "privateIpAddressAllocation": "Dynamic" }]
                nic=azure.network.NetworkInterface("NIC-"+vnet_name, ip_configurations=ip_configurations, resource_group_name=rg.name,
                opts=pulumi.ResourceOptions(depends_on=[virtual_network]))
                osDisk= { "caching": "ReadWrite", "storageAccountType": "Standard_LRS" }
                sourceImageReference = { "publisher": vm['imagePublisher'], "offer": vm['imageOffer'],"sku": vm['imageSku'], "version": "latest"}
                plan = { "name": vm['plan'], "publisher": vm['publisher'], "product": vm['product'] }
                azure.compute.LinuxVirtualMachine("VM-"+vnet_name, name="VM-"+vnet_name, computer_name="VM-"+vnet_name, plan=plan,
                network_interface_ids=[nic.id], size=vm['size'], source_image_reference=sourceImageReference , os_disk=osDisk, admin_username=vm['admin_username'], 
                admin_password=vm['admin_password'], disable_password_authentication=False, resource_group_name=rg.name, 
                opts=pulumi.ResourceOptions(custom_timeouts=pulumi.CustomTimeouts(create='10m')))
                nic_ip[vnet_name]=nic.private_ip_address
             
for peer in peerings:
    for peer_name, peer_dict in peer.items():
        # print (peer_name, peer_dict['local'], peer_dict['remote'])
        peering=azure.network.VirtualNetworkPeering(peer_name, name=peer_name, resource_group_name=rg.name,
            virtual_network_name=peer_dict['local'],
            remote_virtual_network_id=virtual_network_id[peer_dict['remote']])      

pulumi.export("virtual_network_id", virtual_network_id)   
pulumi.export("public_address_id ", public_address_id)
pulumi.export("virtual_network_gateways_id ", virtual_network_gateways_id)       
pulumi.export("nic_ip ", nic_ip) 
'''
PS Azure:\> Get-AzureRmMarketplaceTerms -Publisher "cognosys" -Product "ubuntu-18-04-lts-free" -Name "hardened-ubuntu-18-04-lts-freesku" | Set-AzureRmMarketplaceTerms -Accept
'''


