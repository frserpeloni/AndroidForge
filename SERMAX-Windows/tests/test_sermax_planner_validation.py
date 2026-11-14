import json
import unittest

import sermax_planejador


class PlannerOutputValidationTests(unittest.TestCase):
    def test_accepts_only_complete_allowlisted_steps(self):
        payload = {
            "objetivo": "organizar tarefas",
            "etapas": [
                {
                    "titulo": "Consultar memória",
                    "ferramenta": "consultar_memoria",
                    "verificacao": "Retornar registros encontrados",
                },
                {
                    "titulo": "Responder",
                    "ferramenta": "responder",
                    "verificacao": "Apresentar resultado ao usuário",
                },
            ],
        }
        self.assertEqual(
            sermax_planejador.validar_resposta_plano(
                json.dumps(payload), "organizar tarefas"
            ),
            [
                ("Consultar memória", "consultar_memoria", "Retornar registros encontrados"),
                ("Responder", "responder", "Apresentar resultado ao usuário"),
            ],
        )

    def test_rejects_tool_injection_and_unknown_tools(self):
        for ferramenta in ("shell", "executar_comando", "gravar_arquivo", "", None):
            payload = {
                "etapas": [{
                    "titulo": "Ação",
                    "ferramenta": ferramenta,
                    "verificacao": "Verificar",
                }]
            }
            with self.subTest(ferramenta=ferramenta):
                with self.assertRaises(ValueError):
                    sermax_planejador.validar_resposta_plano(
                        json.dumps(payload), "objetivo"
                    )

    def test_rejects_missing_or_invalid_step_fields(self):
        invalid = [
            {"etapas": []},
            {"etapas": [{}]},
            {"etapas": [{"titulo": "Sem ferramenta", "verificacao": "OK"}]},
            {"etapas": [{"titulo": "Sem verificação", "ferramenta": "responder"}]},
            {"etapas": ["responder"]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises((ValueError, TypeError)):
                    sermax_planejador.validar_resposta_plano(
                        json.dumps(payload), "objetivo"
                    )

    def test_rejects_more_than_four_steps(self):
        payload = {
            "etapas": [{
                "titulo": "Etapa",
                "ferramenta": "responder",
                "verificacao": "OK",
            }] * 5
        }
        with self.assertRaises(ValueError):
            sermax_planejador.validar_resposta_plano(
                json.dumps(payload), "objetivo"
            )

    def test_rejects_oversized_and_non_json_responses(self):
        with self.assertRaises(ValueError):
            sermax_planejador.validar_resposta_plano("x" * 16001, "objetivo")
        with self.assertRaises(ValueError):
            sermax_planejador.validar_resposta_plano("sem json", "objetivo")

    def test_accepts_json_inside_markdown_fence(self):
        payload = {
            "etapas": [{
                "titulo": "Responder",
                "ferramenta": "responder",
                "verificacao": "Resposta apresentada",
            }]
        }
        self.assertEqual(
            len(sermax_planejador.validar_resposta_plano(
                "```json\\n" + json.dumps(payload) + "\\n```",
                "objetivo",
            )),
            1,
        )


if __name__ == "__main__":
    unittest.main()
