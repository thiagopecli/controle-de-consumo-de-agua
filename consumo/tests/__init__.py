import warnings

# Ignora avisos de datetime ingênuo em ambiente de testes
warnings.filterwarnings(
	"ignore",
	message=r"DateTimeField .* received a naive datetime",
	category=RuntimeWarning,
)
