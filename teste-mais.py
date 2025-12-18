import traceback

print(">>> Script iniciado (linha 1)")

try:
    import boto3
    from botocore.exceptions import ClientError
    print(">>> boto3 importado com sucesso")
except Exception as e:
    print("❌ Erro importando boto3/botocore:")
    traceback.print_exc()
    raise SystemExit(1)

ORACLE_CLOUD_BUCKET_NAME = "SFCC-HML"
ORACLE_CLOUD_ENDPOINT = "https://grfhslfoznf.compat.objectstorage.sa-saopaulo-1.oraclecloud.com"
ORACLE_CLOUD_REGION = "sa-saopaulo-1"

def main():
    print(">>> Entrou na função main()")

    # LEIA AS CREDENCIAIS DO AMBIENTE (EXPORT/ENV)
    import os
    access_key = os.getenv("ORACLE_CLOUD_ACCESS_KEY")
    secret_key = os.getenv("ORACLE_CLOUD_SECRET_KEY")

    print(">>> Lendo variáveis de ambiente...")
    print("    ORACLE_CLOUD_ACCESS_KEY está setada?", bool(access_key))
    print("    ORACLE_CLOUD_SECRET_KEY está setada?", bool(secret_key))

    if not access_key or not secret_key:
        print("❌ As variáveis de ambiente ORACLE_CLOUD_ACCESS_KEY e/ou ORACLE_CLOUD_SECRET_KEY não estão definidas.")
        print("   Exemplo no terminal antes de rodar:")
        print('   export ORACLE_CLOUD_ACCESS_KEY="xxxxx"')
        print('   export ORACLE_CLOUD_SECRET_KEY="yyyyy"')
        return

    try:
        s3 = boto3.client(
            "s3",
            region_name=ORACLE_CLOUD_REGION,
            endpoint_url=ORACLE_CLOUD_ENDPOINT,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        print(f">>> Testando conexão com o bucket: {ORACLE_CLOUD_BUCKET_NAME}")

        # Primeiro: testamos listar os buckets (pra ver se conecta no endpoint)
        try:
            buckets = s3.list_buckets()
            print(">>> Conexão OK. Buckets visíveis na conta:")
            for b in buckets.get("Buckets", []):
                print("   -", b["Name"])
        except Exception as e:
            print("⚠ Erro ao listar buckets (mas o endpoint respondeu):")
            traceback.print_exc()

        # Depois: testar acesso ao bucket específico
        try:
            resp = s3.list_objects_v2(Bucket=ORACLE_CLOUD_BUCKET_NAME, MaxKeys=5)
            print("✅ Conexão ao bucket bem-sucedida!")
            if "Contents" in resp:
                print("📁 Objetos encontrados:")
                for obj in resp["Contents"]:
                    print("   -", obj["Key"])
            else:
                print("📁 Bucket vazio ou sem objetos visíveis.")
        except ClientError as e:
            print("❌ Erro de permissão/bucket ao acessar SFCC-HML:")
            traceback.print_exc()

    except Exception as e:
        print("❌ Erro inesperado na conexão:")
        traceback.print_exc()

    print(">>> Fim da função main()")

if __name__ == "__main__":
    print(">>> Chamando main()...")
    main()
    print(">>> Fim do script (depois da main)")


