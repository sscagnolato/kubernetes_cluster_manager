# cluster_manager.py
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml
import time

# =============================================================================
# CONFIGURACOES GLOBAIS
# =============================================================================

# Nomes dos recursos Kubernetes
DEPLOYMENT_NAME = "python-flask-app"
SERVICE_NAME = "python-flask-service"
APP_LABEL = "python-flask"

# Configuracoes do cluster
NAMESPACE = "default"
DEPLOYMENT_REPLICAS = 3

# Configuracoes da aplicacao
CONTAINER_PORT = 8000
SERVICE_PORT = 80
SERVICE_TARGET_PORT = 8000

# =============================================================================
# CLASSE PRINCIPAL
# =============================================================================

class KubernetesManager:
    def __init__(self):
        try:
            config.load_kube_config()
            print("Kubernetes config loaded successfully!")
        except Exception as e:
            print(f"Error loading kube config: {e}")
            raise

    def create_deployment_from_yaml(self, yaml_file):
        """
        Cria deployment e service a partir de um arquivo YAML com multiplos documentos
        """
        try:
            with open(yaml_file, 'r') as file:
                # Carrega todos os documentos YAML
                documents = list(yaml.safe_load_all(file))
                
                for i, doc in enumerate(documents):
                    if doc is None:
                        print(f"Document {i} is empty, skipping...")
                        continue
                    
                    print(f"Processing document {i}: {doc.get('kind', 'Unknown')}")
                    
                    # Determina o tipo de recurso
                    if doc["kind"] == "Deployment":
                        self._create_or_replace_deployment(doc)
                        
                    elif doc["kind"] == "Service":
                        self._create_or_replace_service(doc)
                        
                    else:
                        print(f"Unsupported resource type: {doc['kind']}")
                        
        except FileNotFoundError:
            print(f"Error: File {yaml_file} not found!")
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    def _create_or_replace_deployment(self, deployment_data):
        """
        Cria ou substitui um deployment no cluster Kubernetes
        """
        try:
            api_instance = client.AppsV1Api()
            namespace = deployment_data.get('metadata', {}).get('namespace', NAMESPACE)
            deployment_name = deployment_data['metadata']['name']
            
            # Tenta deletar o deployment existente primeiro
            try:
                api_instance.delete_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace
                )
                print(f"  Deleted existing deployment: {deployment_name}")
                # Aguarda para garantir que os pods sejam terminados
                time.sleep(5)
            except ApiException as e:
                if e.status != 404:  # Ignora se nao existir
                    print(f"  Warning: Could not delete deployment: {e}")
            
            # Cria o novo deployment
            response = api_instance.create_namespaced_deployment(
                body=deployment_data,
                namespace=namespace
            )
            print(f"  Deployment '{deployment_name}' created successfully!")
            print(f"   Namespace: {namespace}")
            print(f"   Replicas: {deployment_data['spec']['replicas']}")
            
        except ApiException as e:
            print(f" Error creating deployment: {e}")
        except Exception as e:
            print(f" Unexpected error creating deployment: {e}")

    def _create_or_replace_service(self, service_data):
        """
        Cria ou substitui um service no cluster Kubernetes
        """
        try:
            api_instance = client.CoreV1Api()
            namespace = service_data.get('metadata', {}).get('namespace', NAMESPACE)
            service_name = service_data['metadata']['name']
            
            # Tenta deletar o serviço existente primeiro
            try:
                api_instance.delete_namespaced_service(
                    name=service_name,
                    namespace=namespace
                )
                print(f"  Deleted existing service: {service_name}")
                # Aguarda um pouco para garantir que foi deletado
                time.sleep(2)
            except ApiException as e:
                if e.status != 404:  # Ignora se não existir
                    print(f"  Warning: Could not delete service: {e}")
            
            # Cria o novo serviço
            response = api_instance.create_namespaced_service(
                body=service_data,
                namespace=namespace
            )
            print(f"  Service '{service_name}' created successfully!")
            print(f"   Namespace: {namespace}")
            print(f"   Type: {service_data['spec']['type']}")
            print(f"   Port: {service_data['spec']['ports'][0]['port']} -> {service_data['spec']['ports'][0]['targetPort']}")
            
        except ApiException as e:
            print(f" Error creating service: {e}")
        except Exception as e:
            print(f" Unexpected error creating service: {e}")

    def get_application_url(self, service_name=SERVICE_NAME):
        """
        Obtem a URL da aplicacao para servicos do tipo NodePort
        """
        try:
            api_instance = client.CoreV1Api()
            
            # Obtém informações do serviço
            service = api_instance.read_namespaced_service(
                name=service_name,
                namespace=NAMESPACE
            )
            
            # Obtem informacoes dos nos
            node_api = client.CoreV1Api()
            nodes = node_api.list_node()
            
            if service.spec.type == "NodePort" and service.spec.ports:
                node_port = service.spec.ports[0].node_port
                
                # Pega o IP do primeiro no (em ambientes de producao, voce pode querer todos)
                if nodes.items:
                    # Tenta diferentes formas de obter o IP do no
                    node_ip = None
                    for address in nodes.items[0].status.addresses:
                        if address.type == "ExternalIP":
                            node_ip = address.address
                            break
                        elif address.type == "InternalIP":
                            node_ip = address.address
                    
                    if node_ip:
                        url = f"http://{node_ip}:{node_port}"
                        print(f" Application URL: {url}")
                        return url
                    else:
                        print(" Could not find node IP address")
                        return None
                else:
                    print(" No nodes found in the cluster")
                    return None
            else:
                print(" Service is not of type NodePort or has no ports defined")
                return None
                
        except ApiException as e:
            print(f" Error getting service information: {e}")
            return None

    def get_detailed_service_info(self, service_name=SERVICE_NAME):
        """
        Obtem informacoes detalhadas do servico
        """
        try:
            api_instance = client.CoreV1Api()
            
            # Obtem informacoes do servico
            service = api_instance.read_namespaced_service(
                name=service_name,
                namespace=NAMESPACE
            )
            
            print(f"\n Detailed Service Information:")
            print(f"   Name: {service.metadata.name}")
            print(f"   Type: {service.spec.type}")
            print(f"   Cluster IP: {service.spec.cluster_ip}")
            
            if service.spec.ports:
                for port in service.spec.ports:
                    print(f"   Port: {port.port} -> {port.target_port}")
                    if service.spec.type == "NodePort" and hasattr(port, 'node_port'):
                        print(f"   Node Port: {port.node_port}")
            
            # Lista todos os nos e seus IPs
            node_api = client.CoreV1Api()
            nodes = node_api.list_node()
            
            print(f"\n  Available Nodes:")
            for i, node in enumerate(nodes.items):
                print(f"   Node {i+1}: {node.metadata.name}")
                for address in node.status.addresses:
                    print(f"     {address.type}: {address.address}")
            
            return service
                
        except ApiException as e:
            print(f" Error getting service information: {e}")
            return None

    def wait_for_pods_ready(self, deployment_name=DEPLOYMENT_NAME, timeout=300):
        """
        Aguarda ate que os pods estejam prontos
        """
        try:
            api_instance = client.AppsV1Api()
            core_api = client.CoreV1Api()
            
            print(f" Waiting for pods to be ready...")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    deployment = api_instance.read_namespaced_deployment(
                        name=deployment_name,
                        namespace=NAMESPACE
                    )
                    
                    available_replicas = deployment.status.available_replicas or 0
                    desired_replicas = deployment.spec.replicas
                    
                    if available_replicas == desired_replicas:
                        print(f" All {available_replicas} pods are ready!")
                        
                        # Lista os pods específicos
                        label_selector = f"app={APP_LABEL}"
                        pods = core_api.list_namespaced_pod(
                            namespace=NAMESPACE,
                            label_selector=label_selector
                        )
                        
                        for pod in pods.items:
                            status = "Ready" if pod.status.phase == "Running" else pod.status.phase
                            print(f"    Pod: {pod.metadata.name} - Status: {status}")
                        
                        return True
                    
                    print(f"     {available_replicas}/{desired_replicas} pods ready...")
                    time.sleep(5)
                
                except ApiException as e:
                    if e.status == 404:
                        print(f"     Deployment not found yet, waiting...")
                        time.sleep(5)
                    else:
                        raise e
            
            print(" Timeout waiting for pods to be ready")
            return False
            
        except Exception as e:
            print(f" Error waiting for pods: {e}")
            return False

    def list_deployments(self):
        """
        Lista todos os deployments no namespace default
        """
        try:
            api_instance = client.AppsV1Api()
            deployments = api_instance.list_namespaced_deployment(namespace=NAMESPACE)
            
            print("\n Current Deployments:")
            if not deployments.items:
                print("   No deployments found.")
            else:
                for deployment in deployments.items:
                    available = deployment.status.available_replicas or 0
                    desired = deployment.spec.replicas
                    print(f"    {deployment.metadata.name} - Replicas: {available}/{desired}")
                    
        except Exception as e:
            print(f"Error listing deployments: {e}")

    def list_services(self):
        """
        Lista todos os services no namespace default
        """
        try:
            api_instance = client.CoreV1Api()
            services = api_instance.list_namespaced_service(namespace=NAMESPACE)
            
            print("\n Current Services:")
            if not services.items:
                print("   No services found.")
            else:
                for service in services.items:
                    service_type = service.spec.type
                    port_info = service.spec.ports[0].port if service.spec.ports else 'N/A'
                    print(f"    {service.metadata.name} - Type: {service_type} - Port: {port_info}")
                    
        except Exception as e:
            print(f"Error listing services: {e}")

    def delete_all_resources(self):
        """
        Deleta todos os recursos criados por este script
        """
        try:
            # Delete deployment
            apps_api = client.AppsV1Api()
            core_api = client.CoreV1Api()
            
            # List and delete deployments
            deployments = apps_api.list_namespaced_deployment(namespace=NAMESPACE)
            for deployment in deployments.items:
                if deployment.metadata.name in [DEPLOYMENT_NAME, "python-deployment"]:
                    apps_api.delete_namespaced_deployment(
                        name=deployment.metadata.name,
                        namespace=NAMESPACE
                    )
                    print(f"  Deleted deployment: {deployment.metadata.name}")
            
            # List and delete services
            services = core_api.list_namespaced_service(namespace=NAMESPACE)
            for service in services.items:
                if service.metadata.name in [SERVICE_NAME]:
                    core_api.delete_namespaced_service(
                        name=service.metadata.name,
                        namespace=NAMESPACE
                    )
                    print(f"  Deleted service: {service.metadata.name}")
                    
        except Exception as e:
            print(f"Error deleting resources: {e}")

    def comprehensive_diagnosis(self):
        """
        Diagnostico completo do cluster
        """
        import subprocess
        
        print("\n Comprehensive Cluster Diagnosis")
        print("=" * 50)
        
        # Verificar nodes
        print("\n Node Status:")
        subprocess.run(["kubectl", "get", "nodes", "-o", "wide"])
        
        # Verificar pods com mais detalhes
        print("\n Pod Status (detailed):")
        subprocess.run(["kubectl", "get", "pods", "-o", "wide", "--all-namespaces"])
        
        # Verificar nossos pods específicos
        print("\n Our Application Pods:")
        subprocess.run(["kubectl", "describe", "pods", "-l", f"app={APP_LABEL}"])
        
        # Verificar eventos
        print("\n Recent Events:")
        subprocess.run(["kubectl", "get", "events", "--sort-by=.metadata.creationTimestamp", "--tail=20"])
        
        # Verificar se a imagem existe nos nodes
        print("\n Image Verification on Nodes:")
        nodes = ["cluster-custom-control-plane", "cluster-custom-worker", "cluster-custom-worker2"]
        for node in nodes:
            try:
                result = subprocess.run(
                    ["docker", "exec", node, "crictl", "images", "|", "grep", "python-flask"],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                print(f"   {node}: {'Image found' if 'python-flask' in result.stdout else 'Image NOT found'}")
            except:
                print(f"   {node}: Could not verify")

    def print_configuration(self):
        """
        Exibe a configuração atual do deployment
        """
        print(f"\n Current Configuration:")
        print(f"   Deployment Name: {DEPLOYMENT_NAME}")
        print(f"   Service Name: {SERVICE_NAME}")
        print(f"   App Label: {APP_LABEL}")
        print(f"   Namespace: {NAMESPACE}")
        print(f"   Replicas: {DEPLOYMENT_REPLICAS}")
        print(f"   Container Port: {CONTAINER_PORT}")
        print(f"   Service Port: {SERVICE_PORT} -> {SERVICE_TARGET_PORT}")

def main():
    """
    Funcao principal para demonstrar o uso do KubernetesManager
    """
    try:
        # Inicializa o gerenciador
        manager = KubernetesManager()
        
        print(" Kubernetes Cluster Manager")
        print("=" * 50)
        
        # Exibe configuração atual
        manager.print_configuration()
        
        # Limpar recursos existentes primeiro
        print("\n Cleaning up existing resources...")
        manager.delete_all_resources()
        time.sleep(5)  # Aguarda a limpeza
        
        # Lista recursos atuais
        manager.list_deployments()
        manager.list_services()
        
        print("\n" + "=" * 50)
        print(" Creating resources from YAML...")
        
        # Cria deployment e service a partir do YAML
        manager.create_deployment_from_yaml("deployment.yaml")
        
        # Aguarda os pods ficarem ready
        manager.wait_for_pods_ready()
        
        print("\n" + "=" * 50)
        print(" Getting application access information...")
        
        # Obtem informacoes detalhadas do servico
        manager.get_detailed_service_info()
        
        # Obtem a URL da aplicacao
        url = manager.get_application_url()
        
        if url:
            print(f"\n Your application should be accessible at:")
            print(f"    {url}")
            print(f"\n Try accessing: {url}/ or {url}/health")
        
        print("\n" + "=" * 50)
        print(" Updated resource status:")
        
        # Lista recursos após criação
        manager.list_deployments()
        manager.list_services()
        
        print("\n" + "=" * 50)
        print(" All operations completed!")
        
        # Opcional: descomente as linhas abaixo para testes
        # print("\n Cleaning up resources...")
        # manager.delete_all_resources()
        
    except Exception as e:
        print(f" Failed to initialize Kubernetes manager: {e}")

if __name__ == "__main__":
    main()

